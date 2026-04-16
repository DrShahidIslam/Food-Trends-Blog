import fs from "node:fs/promises";
import { stripHtml } from "../lib/text.js";

const GALLERY_MARKER = "<!-- pinterest-gallery -->";
const FRENCH_CATEGORY_SLUGS = new Set(["recettes", "pates-a-tartiner", "food-news-fr", "el-mordjene-exclusive-fr"]);
const ENGLISH_CATEGORY_SLUGS = new Set(["recipes", "spreads", "trends", "sweets", "food-news", "el-mordjene-exclusive"]);
const FRENCH_FUNCTION_WORDS = [
  " le ", " la ", " les ", " des ", " une ", " un ", " du ", " et ", " avec ",
  " pour ", " dans ", " sur ", " recette", " ingredients", " etapes", " conseils", " pate", " tartiner"
];
const ENGLISH_FUNCTION_WORDS = [
  " the ", " and ", " with ", " for ", " easy ", " recipe", " ingredients", " tips", " guide", " how to"
];

export function createWordPressClient(config) {
  return {
    async fetchRecentPosts() {
      return this.fetchPostsPage(1, Math.max(config.postsPerRun * 4, 12));
    },

    async fetchPostsPage(page, perPage) {
      const endpoint = new URL("/wp-json/wp/v2/posts", config.siteUrl);
      endpoint.searchParams.set("per_page", String(perPage));
      endpoint.searchParams.set("page", String(page));
      endpoint.searchParams.set("orderby", "date");
      endpoint.searchParams.set("order", "desc");
      endpoint.searchParams.set("_embed", "1");

      const posts = await fetchJson(endpoint, {
        headers: {
          Accept: "application/json",
          Authorization: buildAuthHeader(config),
          "User-Agent": config.wpUserAgent
        }
      }, "fetch posts");
      return posts.map(normalizePost);
    },

    async fetchCategories() {
      const endpoint = new URL("/wp-json/wp/v2/categories", config.siteUrl);
      endpoint.searchParams.set("per_page", "100");
      endpoint.searchParams.set("orderby", "count");
      endpoint.searchParams.set("order", "desc");

      return fetchJson(endpoint, {
        headers: {
          Accept: "application/json",
          Authorization: buildAuthHeader(config),
          "User-Agent": config.wpUserAgent
        }
      }, "fetch categories");
    },

    async uploadMedia(filePath, title) {
      const endpoint = new URL("/wp-json/wp/v2/media", config.siteUrl);
      const fileBuffer = await fs.readFile(filePath);
      const filename = filePath.split(/[/\\]/).pop();

      const response = await fetch(endpoint, {
        method: "POST",
        headers: {
          Authorization: buildAuthHeader(config),
          "User-Agent": config.wpUserAgent,
          "Content-Type": "image/jpeg",
          "Content-Disposition": `attachment; filename="${filename}"`
        },
        body: fileBuffer
      });

      if (!response.ok) {
        const body = await response.text();
        throw new Error(`Media upload failed: ${response.status} ${body}`);
      }

      const media = await parseJsonResponse(response, "media upload");

      await fetch(new URL(`/wp-json/wp/v2/media/${media.id}`, config.siteUrl), {
        method: "POST",
        headers: {
          Authorization: buildAuthHeader(config),
          "User-Agent": config.wpUserAgent,
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ alt_text: title.slice(0, 125) })
      });

      return {
        id: media.id,
        url: media.source_url
      };
    },

    async appendPinterestGallery(postId, postUrl, items) {
      const post = await fetchEditablePost(config, postId);
      const currentContent = post.content?.raw || post.content?.rendered || "";
      const galleryHtml = buildGalleryHtml(postUrl, items);

      let updatedContent = currentContent;
      if (currentContent.includes(GALLERY_MARKER)) {
        updatedContent = replacePinterestGallery(currentContent, galleryHtml);
        if (updatedContent === currentContent) {
          return { updated: false };
        }
      } else {
        updatedContent = `${currentContent}\n\n${galleryHtml}`;
      }

      const endpoint = new URL(`/wp-json/wp/v2/posts/${postId}`, config.siteUrl);

      const response = await fetch(endpoint, {
        method: "POST",
        headers: {
          Authorization: buildAuthHeader(config),
          "User-Agent": config.wpUserAgent,
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ content: updatedContent })
      });

      if (!response.ok) {
        const body = await response.text();
        throw new Error(`Post update failed: ${response.status} ${body}`);
      }

      return { updated: true };
    }
  };
}

function buildAuthHeader(config) {
  const token = Buffer.from(`${config.wpUsername}:${config.wpAppPassword}`).toString("base64");
  return `Basic ${token}`;
}

async function fetchEditablePost(config, postId) {
  const endpoint = new URL(`/wp-json/wp/v2/posts/${postId}`, config.siteUrl);
  endpoint.searchParams.set("context", "edit");

  const response = await fetch(endpoint, {
    headers: {
      Accept: "application/json",
      Authorization: buildAuthHeader(config)
    }
  });

  if (!response.ok) {
    const body = await safeReadBody(response);
    throw new Error(`Failed to fetch post ${postId}: ${response.status} ${response.statusText}${body}`);
  }

  return parseJsonResponse(response, `fetch post ${postId}`);
}

function buildGalleryHtml(postUrl, items) {
  const blocks = items.map((item) => {
    const title = escapeAttribute(item.pinTitle);
    const description = escapeAttribute(item.pinDescription || "");
    const scheduledFor = escapeAttribute(item.scheduledFor || "");
    const keyword = escapeAttribute(item.primaryKeyword || "");
    const variant = escapeAttribute(item.variant || "");
    const board = escapeAttribute(item.boardName || "");

    return `<p><a href="${postUrl}"><img src="${item.mediaUrl}" alt="${title}" data-pin-title="${title}" data-pin-description="${description}" data-pin-scheduled="${scheduledFor}" data-pin-keyword="${keyword}" data-pin-variant="${variant}" data-pin-board="${board}" /></a></p>`;
  }).join("\n");

  return `${GALLERY_MARKER}\n<div class="pinterest-gallery">\n${blocks}\n</div>`;
}
function replacePinterestGallery(content, galleryHtml) {
  const pattern = new RegExp(`${GALLERY_MARKER}\\s*<div class=\"pinterest-gallery\">[\\s\\S]*?<\\/div>`, "i");
  if (!pattern.test(content)) {
    return content;
  }
  return content.replace(pattern, galleryHtml);
}
async function fetchJson(endpoint, options, context) {
  const response = await fetch(endpoint, options);
  if (!response.ok) {
    const body = await safeReadBody(response);
    throw new Error(`Failed to ${context}: ${response.status} ${response.statusText}${body}`);
  }

  return parseJsonResponse(response, context);
}

async function parseJsonResponse(response, context) {
  const text = await response.text();
  try {
    return JSON.parse(text);
  } catch {
    const contentType = response.headers.get("content-type") || "unknown";
    const snippet = text.trim().slice(0, 160);
    throw new Error(`Unexpected response for ${context}: content-type=${contentType} body="${snippet}"`);
  }
}

async function safeReadBody(response) {
  try {
    const text = await response.text();
    const snippet = text.trim().slice(0, 160);
    return snippet ? ` body="${snippet}"` : "";
  } catch {
    return "";
  }
}
function normalizePost(post) {
  const terms = post._embedded?.["wp:term"] || [];
  const allTerms = terms.flat();
  const categories = allTerms.filter((term) => term.taxonomy === "category");
  const tags = allTerms.filter((term) => term.taxonomy === "post_tag");
  const featuredImage = post._embedded?.["wp:featuredmedia"]?.[0]?.source_url || "";
  const title = stripHtml(post.title?.rendered || "");
  const excerpt = stripHtml(post.excerpt?.rendered || "");
  const contentHtml = post.content?.rendered || "";

  return {
    id: post.id,
    date: post.date_gmt || post.date,
    status: post.status,
    url: post.link,
    slug: post.slug,
    title,
    excerpt,
    contentHtml,
    featuredImage,
    language: inferLanguage(post, categories, title, excerpt, contentHtml),
    categories: categories.map((term) => ({ id: term.id, name: term.name, slug: term.slug })),
    tags: tags.map((term) => term.name)
  };
}

function inferLanguage(post, categories, title, excerpt, contentHtml) {
  if (post.lang && ["en", "fr"].includes(String(post.lang).toLowerCase())) {
    return String(post.lang).toLowerCase();
  }

  const slugs = categories.map((category) => category.slug.toLowerCase());
  if (slugs.some((slug) => FRENCH_CATEGORY_SLUGS.has(slug))) {
    return "fr";
  }
  if (slugs.some((slug) => ENGLISH_CATEGORY_SLUGS.has(slug))) {
    return "en";
  }

  const textSample = ` ${title} ${excerpt} ${stripHtml(contentHtml).slice(0, 500)} `.toLowerCase();
  let frenchScore = 0;
  let englishScore = 0;

  for (const marker of FRENCH_FUNCTION_WORDS) {
    if (textSample.includes(marker)) {
      frenchScore += 1;
    }
  }
  for (const marker of ENGLISH_FUNCTION_WORDS) {
    if (textSample.includes(marker)) {
      englishScore += 1;
    }
  }

  if (/[éèêàùçôî]/i.test(`${title} ${excerpt}`)) {
    frenchScore += 2;
  }

  return frenchScore > englishScore ? "fr" : "en";
}

function escapeAttribute(value) {
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll('"', "&quot;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}






