const CATEGORY_SLUGS = {
  recipes_en: new Set(["recipes"]),
  recipes_fr: new Set(["recettes"]),
  spreads_en: new Set(["spreads"]),
  spreads_fr: new Set(["pates-a-tartiner"]),
  trends: new Set(["trends"]),
  sweets: new Set(["sweets"]),
  foodNews: new Set(["food-news", "food-news-fr"]),
  elMordjene: new Set(["el-mordjene-exclusive", "el-mordjene-exclusive-fr"])
};

const SPREAD_KEYWORDS = [
  "hazelnut spread",
  "chocolate spread",
  "nutella",
  "cebon",
  "el mordjene spread",
  "homemade spread"
];

const FRENCH_SPREAD_KEYWORDS = [
  "pate a tartiner",
  "pates a tartiner",
  "tartiner",
  "noisette"
];

const RECIPE_KEYWORDS = [
  "recipe",
  "recette",
  "how to make",
  "ingredients",
  "instructions",
  "copycat",
  "croissant",
  "pastry",
  "dessert",
  "ice cream",
  "donuts"
];

const TREND_KEYWORDS = [
  "trend",
  "viral",
  "cafe",
  "launch",
  "taking over",
  "new treat",
  "what you need to know"
];

const SWEETS_KEYWORDS = [
  "dessert",
  "sweet",
  "chocolate",
  "strawberries",
  "candy",
  "bakery",
  "pastry",
  "croissant",
  "ice cream",
  "dates"
];

const NON_PIN_WORTHY_KEYWORDS = [
  "recall",
  "lawsuit",
  "ban",
  "banned",
  "regulation",
  "food safety",
  "nationwide recall"
];

export function classifyPost(post, boards) {
  const primaryHaystack = [
    post.title,
    post.excerpt,
    post.slug,
    post.tags.join(" "),
    post.categories.map((category) => `${category.name} ${category.slug}`).join(" ")
  ].join(" ").toLowerCase();
  const secondaryHaystack = [post.excerpt, post.contentHtml].join(" ").toLowerCase();
  const categorySlugs = new Set(post.categories.map((category) => category.slug.toLowerCase()));

  const hasCategory = (group) => [...group].some((slug) => categorySlugs.has(slug));
  const isFrench = post.language === "fr";
  const isFoodNews = hasCategory(CATEGORY_SLUGS.foodNews);
  const isElMordjene = hasCategory(CATEGORY_SLUGS.elMordjene);
  const isCategoryRecipeEn = hasCategory(CATEGORY_SLUGS.recipes_en);
  const isCategoryRecipeFr = hasCategory(CATEGORY_SLUGS.recipes_fr);
  const isCategorySpreadEn = hasCategory(CATEGORY_SLUGS.spreads_en);
  const isCategorySpreadFr = hasCategory(CATEGORY_SLUGS.spreads_fr);
  const isCategoryTrend = hasCategory(CATEGORY_SLUGS.trends);
  const isCategorySweet = hasCategory(CATEGORY_SLUGS.sweets);

  const isFrenchSpread = FRENCH_SPREAD_KEYWORDS.some((keyword) => primaryHaystack.includes(keyword));
  const isSpread = isCategorySpreadEn || isCategorySpreadFr || SPREAD_KEYWORDS.some((keyword) => primaryHaystack.includes(keyword)) || isFrenchSpread;
  const isRecipe = isCategoryRecipeEn || isCategoryRecipeFr || RECIPE_KEYWORDS.some((keyword) => primaryHaystack.includes(keyword));
  const isTrend = isCategoryTrend || TREND_KEYWORDS.some((keyword) => primaryHaystack.includes(keyword));
  const isSweet = isCategorySweet || SWEETS_KEYWORDS.some((keyword) => primaryHaystack.includes(keyword) || secondaryHaystack.includes(keyword));
  const isNonVisualNews = isFoodNews || NON_PIN_WORTHY_KEYWORDS.some((keyword) => primaryHaystack.includes(keyword) || secondaryHaystack.includes(keyword));

  const pinWorthinessScore =
    (isRecipe ? 3 : 0) +
    (isSpread ? 3 : 0) +
    (isTrend ? 2 : 0) +
    (isSweet ? 2 : 0) +
    (post.featuredImage ? 1 : 0) -
    (isNonVisualNews ? 5 : 0);

  let contentType = "trend";
  let boardKey = "sweets_trends";

  if (isCategorySpreadFr || (isFrench && isFrenchSpread)) {
    contentType = "spread";
    boardKey = "spreads_fr";
  } else if (isCategorySpreadEn || (isSpread && !isRecipe && !isTrend)) {
    contentType = "spread";
    boardKey = "spreads_en";
  } else if (isCategoryRecipeFr) {
    contentType = "recipe";
    boardKey = "recipes_fr";
  } else if (isCategoryRecipeEn || (isRecipe && !isTrend)) {
    contentType = "recipe";
    boardKey = "recipes_en";
  } else if (isTrend || isSweet || isElMordjene) {
    contentType = "trend";
    boardKey = "sweets_trends";
  }

  let shouldPin = pinWorthinessScore >= 2 && !isNonVisualNews;

  if (isCategorySpreadFr || isCategorySpreadEn || isCategoryRecipeFr || isCategoryRecipeEn) {
    shouldPin = !isNonVisualNews;
  }

  return {
    shouldPin,
    contentType,
    boardKey,
    boardName: boards[boardKey],
    language: isFrench ? "fr" : "en",
    pinWorthinessScore
  };
}
