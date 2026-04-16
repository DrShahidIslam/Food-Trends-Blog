export function stripHtml(value) {
  return String(value || "")
    .replace(/<[^>]*>/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

export function slugify(value) {
  return String(value || "")
    .toLowerCase()
    .normalize("NFKD")
    .replace(/[^\w\s-]/g, "")
    .replace(/[\s_-]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

export function clampText(value, maxLength) {
  const text = String(value || "").trim();
  if (!text) {
    return "";
  }

  if (text.length <= maxLength) {
    return text;
  }

  return `${text.slice(0, Math.max(1, maxLength - 3)).trim()}...`;
}

export function extractHeadingsFromHtml(html) {
  const matches = String(html || "").match(/<h[2-3][^>]*>(.*?)<\/h[2-3]>/gims) || [];
  return matches.map((match) => stripHtml(match)).filter(Boolean).slice(0, 8);
}

export function extractListItemsFromHtml(html) {
  const matches = String(html || "").match(/<li[^>]*>(.*?)<\/li>/gims) || [];
  return matches.map((match) => stripHtml(match)).filter(Boolean).slice(0, 8);
}

export function extractSentences(value, limit = 6) {
  return stripHtml(value)
    .split(/(?<=[.!?])\s+/)
    .map((part) => part.trim())
    .filter((part) => part.length > 20)
    .slice(0, limit);
}

export function buildKeywordSet(post) {
  const pools = [
    post.title,
    post.excerpt,
    ...(post.tags || []),
    ...(post.categories || []).map((category) => category.name),
    ...extractHeadingsFromHtml(post.contentHtml),
    ...extractListItemsFromHtml(post.contentHtml).slice(0, 4)
  ];

  const stopwords = getStopwords(post.language);
  const phraseSeeds = pools
    .flatMap((value) => splitCandidatePhrases(value))
    .map((value) => normalizeKeyword(value))
    .filter(Boolean)
    .filter((value) => value.length >= 3)
    .filter((value) => !stopwords.has(value));

  const deduped = [];
  for (const item of phraseSeeds) {
    if (!deduped.includes(item)) {
      deduped.push(item);
    }
  }

  const longTail = deduped
    .filter((item) => item.includes(" "))
    .slice(0, 8);

  const shortTerms = deduped
    .filter((item) => !item.includes(" "))
    .slice(0, 8);

  return [...longTail, ...shortTerms].slice(0, 10);
}

export function pickPrimaryKeyword(post, classification) {
  const keywords = buildKeywordSet(post);
  const title = normalizeKeyword(post.title);
  const titleParts = splitCandidatePhrases(post.title)
    .map((value) => normalizeKeyword(value))
    .filter(Boolean);

  const titleLongTail = titleParts.find((value) => value.split(" ").length >= 2 && value.length >= 8);
  if (titleLongTail) {
    return titleLongTail;
  }

  const strongKeyword = keywords.find((value) => value.split(" ").length >= 2);
  if (strongKeyword) {
    return strongKeyword;
  }

  if (classification.contentType === "spread") {
    return post.language === "fr" ? "pate a tartiner" : "chocolate spread";
  }

  if (classification.contentType === "recipe") {
    return post.language === "fr" ? "recette facile" : "easy recipe";
  }

  return title || (post.language === "fr" ? "douceur tendance" : "trending sweet");
}

function splitCandidatePhrases(value) {
  return String(value || "")
    .split(/[|,:;()\-]+/)
    .map((part) => part.trim())
    .filter(Boolean);
}

function normalizeKeyword(value) {
  return String(value || "")
    .normalize("NFKD")
    .replace(/[^\w\s]/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .toLowerCase();
}

function getStopwords(language) {
  const english = [
    "the", "and", "with", "from", "that", "this", "your", "have", "into", "about", "more", "than", "what", "when", "where", "easy", "best", "guide", "tips"
  ];
  const french = [
    "les", "des", "une", "avec", "dans", "pour", "plus", "tout", "bien", "votre", "guide", "conseils", "recette", "recettes"
  ];

  return new Set(language === "fr" ? french : english);
}
