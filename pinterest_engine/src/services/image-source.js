import { clampText } from "../lib/text.js";

export async function resolveImageSource(asset, config, options = {}) {
  const queries = buildQueries(asset);
  const candidates = [];
  const excludeUrls = new Set((options.excludeUrls || []).filter(Boolean));

  if (asset.featuredImage && !excludeUrls.has(asset.featuredImage)) {
    candidates.push(await buildFeaturedCandidate(asset));
  }

  const stockCandidates = await findStockCandidates(queries, config, excludeUrls);
  candidates.push(...stockCandidates);

  const best = pickBestCandidate(candidates, excludeUrls);
  if (best) {
    return best;
  }

  if (options.allowFallback) {
    return pickBestCandidate(candidates) || null;
  }

  return null;
}

function pickBestCandidate(candidates, excludeUrls) {
  const filtered = Array.isArray(candidates) ? candidates.filter((candidate) => Boolean(candidate?.url)) : [];
  const usable = excludeUrls ? filtered.filter((candidate) => !excludeUrls.has(candidate.url)) : filtered;
  return usable.sort((a, b) => b.score - a.score)[0] || null;
}

async function buildFeaturedCandidate(asset) {
  const meta = await inspectImage(asset.featuredImage);
  const score = 68 + scoreDimensions(meta.width, meta.height) + (isLikelyGenericFeatured(asset.featuredImage) ? -18 : 8);

  return {
    provider: "featured",
    url: asset.featuredImage,
    score,
    attribution: "site",
    width: meta.width,
    height: meta.height,
    reason: isLikelyGenericFeatured(asset.featuredImage) ? "generic-site-image" : "strong-site-image"
  };
}

async function findStockCandidates(queries, config, excludeUrls) {
  const candidates = [];

  if (config.pexelsApiKey) {
    for (const query of queries) {
      const candidate = await searchPexels(query, config.pexelsApiKey, excludeUrls);
      if (candidate) {
        candidates.push(candidate);
      }
      if (candidates.some((item) => item.provider === "pexels")) {
        break;
      }
    }
  }

  if (config.pixabayApiKey) {
    for (const query of queries) {
      const candidate = await searchPixabay(query, config.pixabayApiKey, excludeUrls);
      if (candidate) {
        candidates.push(candidate);
      }
      if (candidates.some((item) => item.provider === "pixabay")) {
        break;
      }
    }
  }

  return candidates.map((candidate) => adjustStockScore(candidate, config));
}

function adjustStockScore(candidate, config) {
  let score = candidate.score + scoreDimensions(candidate.width, candidate.height);

  if (candidate.queryWords >= 3) {
    score += 6;
  }

  if (config.imageSourceMode === "stock-first") {
    score += 8;
  }

  return {
    ...candidate,
    score
  };
}

function buildQueries(asset) {
  const seeds = [
    asset.primaryKeyword,
    ...(asset.searchTags || []),
    asset.pinTitle,
    asset.boardName,
    asset.contentType === "spread" ? (asset.language === "fr" ? "pate a tartiner" : "chocolate spread jar") : "",
    asset.contentType === "recipe" ? "food recipe close up" : "",
    asset.contentType === "trend" ? "dessert food close up" : ""
  ].filter(Boolean);

  const cleaned = [];
  for (const seed of seeds) {
    const value = clampText(cleanSearch(seed), 60);
    if (value && !cleaned.includes(value)) {
      cleaned.push(value);
    }
  }

  return cleaned.slice(0, 8);
}

async function searchPexels(query, apiKey, excludeUrls) {
  try {
    const endpoint = new URL("https://api.pexels.com/v1/search");
    endpoint.searchParams.set("query", query);
    endpoint.searchParams.set("per_page", "10");
    endpoint.searchParams.set("orientation", "portrait");

    const response = await fetch(endpoint, {
      headers: {
        Authorization: apiKey
      }
    });

    if (!response.ok) {
      return null;
    }

    const data = await response.json();
    const photos = Array.isArray(data.photos) ? data.photos : [];
    const photo = photos.find((item) => {
      const url = item.src?.large2x || item.src?.portrait || item.src?.large;
      if (!url) return false;
      return excludeUrls ? !excludeUrls.has(url) : true;
    });
    if (!photo) {
      return null;
    }

    return {
      provider: "pexels",
      url: photo.src.large2x || photo.src.portrait || photo.src.large,
      score: 80,
      attribution: `Pexels / ${photo.photographer || "unknown"}`,
      sourcePage: photo.url || "",
      width: Number(photo.width) || 0,
      height: Number(photo.height) || 0,
      query,
      queryWords: query.split(/\s+/).filter(Boolean).length
    };
  } catch {
    return null;
  }
}

async function searchPixabay(query, apiKey, excludeUrls) {
  try {
    const endpoint = new URL("https://pixabay.com/api/");
    endpoint.searchParams.set("key", apiKey);
    endpoint.searchParams.set("q", query);
    endpoint.searchParams.set("image_type", "photo");
    endpoint.searchParams.set("orientation", "vertical");
    endpoint.searchParams.set("per_page", "10");
    endpoint.searchParams.set("safesearch", "true");

    const response = await fetch(endpoint);
    if (!response.ok) {
      return null;
    }

    const data = await response.json();
    const hits = Array.isArray(data.hits) ? data.hits : [];
    const hit = hits.find((item) => {
      const url = item.largeImageURL || item.webformatURL;
      if (!url) return false;
      return excludeUrls ? !excludeUrls.has(url) : true;
    });
    if (!hit) {
      return null;
    }

    return {
      provider: "pixabay",
      url: hit.largeImageURL || hit.webformatURL,
      score: 74,
      attribution: `Pixabay / ${hit.user || "unknown"}`,
      sourcePage: hit.pageURL || "",
      width: Number(hit.imageWidth) || 0,
      height: Number(hit.imageHeight) || 0,
      query,
      queryWords: query.split(/\s+/).filter(Boolean).length
    };
  } catch {
    return null;
  }
}

async function inspectImage(url) {
  try {
    const response = await fetch(url, {
      method: "HEAD",
      headers: {
        Accept: "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8"
      }
    });

    if (!response.ok) {
      return { width: 0, height: 0 };
    }

    const width = Number(response.headers.get("x-img-width") || 0);
    const height = Number(response.headers.get("x-img-height") || 0);
    return { width, height };
  } catch {
    return { width: 0, height: 0 };
  }
}

function scoreDimensions(width, height) {
  if (!width || !height) {
    return 0;
  }

  if (height > width) {
    return 10;
  }

  if (height === width) {
    return 3;
  }

  return -4;
}

function isLikelyGenericFeatured(url) {
  const value = String(url || "").toLowerCase();
  return ["placeholder", "default", "generated", "featured-image", "stock"].some((part) => value.includes(part));
}

function cleanSearch(value) {
  return String(value || "")
    .replace(/\|/g, " ")
    .replace(/[^\w\s-]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}
