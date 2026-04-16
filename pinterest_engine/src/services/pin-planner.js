import {
  buildKeywordSet,
  clampText,
  extractHeadingsFromHtml,
  extractListItemsFromHtml,
  extractSentences,
  pickPrimaryKeyword
} from "../lib/text.js";

export function buildPinPlan(post, classification, config, options = {}) {
  const headings = extractHeadingsFromHtml(post.contentHtml);
  const listItems = extractListItemsFromHtml(post.contentHtml);
  const sentences = extractSentences(`${post.excerpt} ${post.contentHtml}`);
  const primaryKeyword = pickPrimaryKeyword(post, classification);
  const keywordSet = buildKeywordSet(post);
  const firstHeading = headings[0] || sentences[0] || post.excerpt || post.title;
  const listLead = listItems[0] || headings[1] || sentences[1] || firstHeading;
  const guideLead = headings[2] || sentences[2] || post.excerpt || firstHeading;

  const variants = [
    {
      key: "hero",
      angle: post.language === "fr" ? "hero principal" : "main hook",
      overlayTitle: clampText(buildHeroOverlay(post, primaryKeyword), 56),
      overlaySubtitle: clampText(firstHeading, 70),
      pinTitle: clampText(buildHeroPinTitle(post, primaryKeyword), 100),
      pinDescription: clampText(buildHeroDescription(post, primaryKeyword, keywordSet), 320),
      primaryKeyword,
      supportingKeywords: keywordSet.slice(0, 5)
    },
    {
      key: "list",
      angle: post.language === "fr" ? "points a retenir" : "saveable summary",
      overlayTitle: clampText(buildListTitle(post, classification, primaryKeyword), 56),
      overlaySubtitle: clampText(listLead, 70),
      pinTitle: clampText(`${buildListTitle(post, classification, primaryKeyword)} | ${post.title}`, 100),
      pinDescription: clampText(buildListDescription(post, primaryKeyword, keywordSet), 320),
      primaryKeyword,
      supportingKeywords: keywordSet.slice(1, 6)
    },
    {
      key: "guide",
      angle: post.language === "fr" ? "guide pratique" : "practical guide",
      overlayTitle: clampText(buildGuideTitle(post, classification, primaryKeyword), 56),
      overlaySubtitle: clampText(guideLead, 70),
      pinTitle: clampText(`${buildGuideTitle(post, classification, primaryKeyword)} | ${post.title}`, 100),
      pinDescription: clampText(buildGuideDescription(post, primaryKeyword, keywordSet), 320),
      primaryKeyword,
      supportingKeywords: keywordSet.slice(2, 7)
    }
  ];

  return variants.map((variant, index) => ({
    ...variant,
    boardKey: classification.boardKey,
    boardName: classification.boardName,
    scheduledFor: scheduleDate(options.scheduleAnchorDate || post.date, index, config),
    sourcePostId: post.id
  }));
}

function buildHeroOverlay(post, primaryKeyword) {
  if (post.language === "fr") {
    return titleCase(`${primaryKeyword} a essayer`);
  }

  return titleCase(`${primaryKeyword} worth trying`);
}

function buildHeroPinTitle(post, primaryKeyword) {
  if (post.title.toLowerCase().includes(primaryKeyword.toLowerCase())) {
    return post.title;
  }

  return `${titleCase(primaryKeyword)} | ${post.title}`;
}

function buildHeroDescription(post, primaryKeyword, keywords) {
  const extras = keywords.filter((value) => value !== primaryKeyword).slice(0, 3).join(", ");
  if (post.language === "fr") {
    return `${titleCase(primaryKeyword)} : decouvrez cette idee gourmande, ses etapes, ses astuces et pourquoi elle donne envie de cliquer. ${extras}`.trim();
  }

  return `${titleCase(primaryKeyword)} with a click-worthy angle, useful details, and a more tempting way to explore the full post. ${extras}`.trim();
}

function buildListTitle(post, classification, primaryKeyword) {
  if (classification.contentType === "recipe") {
    return post.language === "fr" ? `${titleCase(primaryKeyword)} en detail` : `${titleCase(primaryKeyword)} breakdown`;
  }

  if (classification.contentType === "spread") {
    return post.language === "fr" ? `${titleCase(primaryKeyword)} en bref` : `${titleCase(primaryKeyword)} at a glance`;
  }

  return post.language === "fr" ? `Pourquoi ${primaryKeyword}` : `Why ${primaryKeyword}`;
}

function buildListDescription(post, primaryKeyword, keywords) {
  const extras = keywords.filter((value) => value !== primaryKeyword).slice(0, 4).join(", ");
  if (post.language === "fr") {
    return `Enregistrez cette epingle sur ${primaryKeyword} pour retrouver les points utiles, les saveurs, les ingredients ou les infos cles. ${extras}`.trim();
  }

  return `Save this pin for a quick ${primaryKeyword} summary with key details, ingredients, texture notes, or standout talking points. ${extras}`.trim();
}

function buildGuideTitle(post, classification, primaryKeyword) {
  if (classification.contentType === "recipe") {
    return post.language === "fr" ? `Reussir ${primaryKeyword}` : `Make ${primaryKeyword} better`;
  }

  if (classification.contentType === "spread") {
    return post.language === "fr" ? `${titleCase(primaryKeyword)} et astuces` : `${titleCase(primaryKeyword)} tips`;
  }

  return post.language === "fr" ? `${titleCase(primaryKeyword)} avant de cliquer` : `Before you try ${primaryKeyword}`;
}

function buildGuideDescription(post, primaryKeyword, keywords) {
  const extras = keywords.filter((value) => value !== primaryKeyword).slice(0, 4).join(", ");
  if (post.language === "fr") {
    return `Conseils rapides, points de texture, idees utiles et angle plus fort autour de ${primaryKeyword}. ${extras}`.trim();
  }

  return `Quick tips, stronger context, and a more persuasive angle around ${primaryKeyword}. ${extras}`.trim();
}

function titleCase(value) {
  return String(value || "")
    .split(" ")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

export function scheduleDate(postDate, index, config) {
  const offsets = [
    config.queueSpacingDays.first,
    config.queueSpacingDays.second,
    config.queueSpacingDays.third
  ];
  const date = new Date(postDate);
  date.setUTCDate(date.getUTCDate() + (offsets[index] || 0));

  const slot = Array.isArray(config.pinHourSlots) ? config.pinHourSlots[index] : undefined;
  if (Number.isFinite(slot)) {
    date.setUTCHours(slot, 0, 0, 0);
  }

  return date.toISOString();
}

