import path from "node:path";

const DEFAULT_BOARDS = {
  recipes_en: "Recipes",
  recipes_fr: "Recettes",
  spreads_en: "Spreads",
  spreads_fr: "Pates a tartiner",
  sweets_trends: "Sweets & Trends"
};

export function loadConfig() {
  const siteUrl = required("SITE_URL");
  const publishMode = normalizePublishMode(process.env.PUBLISH_MODE);

  return {
    siteUrl,
    wpUsername: required("WP_USERNAME"),
    wpAppPassword: required("WP_APP_PASSWORD"),
    wpUserAgent: process.env.WP_USER_AGENT?.trim() || "El-Mordjene-Pinterest-Bot/1.0",
    geminiApiKey: process.env.GEMINI_API_KEY?.trim() || "",
    geminiTextModel: process.env.GEMINI_TEXT_MODEL?.trim() || "gemini-2.0-flash",
    pexelsApiKey: process.env.PEXELS_API_KEY?.trim() || "",
    pixabayApiKey: process.env.PIXABAY_API_KEY?.trim() || "",
    imageSourceMode: process.env.IMAGE_SOURCE_MODE?.trim() || "featured-first",
    publishMode,
    lookbackHours: numberFromEnv("LOOKBACK_HOURS", 48),
    postsPerRun: numberFromEnv("POSTS_PER_RUN", 6),
    renderBatchSize: numberFromEnv("RENDER_BATCH_SIZE", 9),
    publishBatchSize: numberFromEnv("PUBLISH_BATCH_SIZE", 9),
    maxPinsPerDay: numberFromEnv("MAX_PINS_PER_DAY", 15),
    maxPostsPerDay: numberFromEnv("MAX_POSTS_PER_DAY", 5),
    assetsDir: path.resolve(process.env.ASSETS_DIR?.trim() || "data/assets"),
    exportsDir: path.resolve(process.env.EXPORTS_DIR?.trim() || "data/exports"),
    statePath: path.resolve(process.env.STATE_PATH?.trim() || "data/state.json"),
    pinHourSlots: [
      numberFromEnv("PIN_HOUR_1", 9),
      numberFromEnv("PIN_HOUR_2", 14),
      numberFromEnv("PIN_HOUR_3", 19)
    ],
    backfillPostsPerRun: numberFromEnv("BACKFILL_POSTS_PER_RUN", 12),
    backfillMaxPages: numberFromEnv("BACKFILL_MAX_PAGES", 10),
    backfillStartDelayHours: numberFromEnv("BACKFILL_START_DELAY_HOURS", 24),
    backfillPostIntervalHours: numberFromEnv("BACKFILL_POST_INTERVAL_HOURS", 24),
    backfillCategorySlugs: listFromEnv("BACKFILL_CATEGORY_SLUGS"),
    queueSpacingDays: {
      first: numberFromEnv("PIN_DAY_1", 0),
      second: numberFromEnv("PIN_DAY_2", 2),
      third: numberFromEnv("PIN_DAY_3", 7)
    },
    boards: {
      recipes_en: process.env.BOARD_RECIPES_EN?.trim() || DEFAULT_BOARDS.recipes_en,
      recipes_fr: process.env.BOARD_RECIPES_FR?.trim() || DEFAULT_BOARDS.recipes_fr,
      spreads_en: process.env.BOARD_SPREADS_EN?.trim() || DEFAULT_BOARDS.spreads_en,
      spreads_fr: process.env.BOARD_SPREADS_FR?.trim() || DEFAULT_BOARDS.spreads_fr,
      sweets_trends: process.env.BOARD_SWEETS_TRENDS?.trim() || DEFAULT_BOARDS.sweets_trends
    }
  };
}

function required(name) {
  const value = process.env[name]?.trim();
  if (!value) {
    throw new Error(`Missing required environment variable: ${name}`);
  }
  return value;
}

function listFromEnv(name) {
  const value = process.env[name];
  if (!value) {
    return [];
  }
  return value.split(",").map((part) => part.trim()).filter(Boolean);
}

function numberFromEnv(name, fallback) {
  const value = process.env[name]?.trim();
  if (!value) {
    return fallback;
  }

  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function normalizePublishMode(value) {
  const mode = String(value || "csv").trim().toLowerCase();
  return mode === "rss" ? "rss" : "csv";
}