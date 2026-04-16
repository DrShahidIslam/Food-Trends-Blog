import fs from "node:fs/promises";
import path from "node:path";

const TARGET_FEEDS = [
  { boardKey: "recipes_en", purpose: "English recipes", slug: "recipes" },
  { boardKey: "recipes_fr", purpose: "French recipes", slug: "recettes" },
  { boardKey: "spreads_en", purpose: "English spreads", slug: "spreads" },
  { boardKey: "spreads_fr", purpose: "French spreads", slug: "pates-a-tartiner" },
  { boardKey: "sweets_trends", purpose: "Sweets and trends", slug: "trends", optionalSecondarySlug: "sweets" }
];

export async function buildFeedPlan({ config, wordpress }) {
  const categories = await wordpress.fetchCategories();
  const bySlug = new Map(categories.map((category) => [category.slug, category]));

  const feedPlan = TARGET_FEEDS.map((target) => {
    const primary = bySlug.get(target.slug) || null;
    const secondary = target.optionalSecondarySlug ? bySlug.get(target.optionalSecondarySlug) || null : null;

    return {
      board: config.boards[target.boardKey],
      purpose: target.purpose,
      primaryFeed: primary ? toFeed(config.siteUrl, primary) : null,
      secondaryFeed: secondary ? toFeed(config.siteUrl, secondary) : null,
      ready: Boolean(primary)
    };
  });

  const output = {
    generatedAt: new Date().toISOString(),
    feedPlan,
    categories: categories.map((category) => ({
      id: category.id,
      name: category.name,
      slug: category.slug,
      count: category.count,
      feedUrl: `${config.siteUrl.replace(/\/$/, "")}/category/${category.slug}/feed/`
    }))
  };

  const outputPath = path.join(config.exportsDir, "feed-plan.json");
  await fs.mkdir(config.exportsDir, { recursive: true });
  await fs.writeFile(outputPath, JSON.stringify(output, null, 2), "utf8");
  return { output, outputPath };
}

function toFeed(siteUrl, category) {
  return {
    categoryId: category.id,
    categoryName: category.name,
    categorySlug: category.slug,
    categoryCount: category.count,
    feedUrl: `${siteUrl.replace(/\/$/, "")}/category/${category.slug}/feed/`
  };
}
