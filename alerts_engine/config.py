"""
Central configuration for the El-Mordjene News Agent.
All settings, keywords, RSS feeds, and thresholds are defined here.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# API Keys
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
NEWS_API_KEY = os.getenv("NEWS_API_KEY") or os.getenv("newsapi_key")

_gemini_keys_env = os.getenv("GEMINI_API_KEYS", os.getenv("GEMINI_API_KEY", ""))
GEMINI_API_KEYS = [k.strip() for k in _gemini_keys_env.split(",") if k.strip()]
GEMINI_API_KEY = GEMINI_API_KEYS[0] if GEMINI_API_KEYS else None

WP_URL = os.getenv("WP_BASE_URL", "https://el-mordjene.info").rstrip("/")
WP_USERNAME = os.getenv("WP_USERNAME")
WP_APP_PASSWORD = os.getenv("WP_APP_PASSWORD")
WP_PUBLISH_WEBHOOK_URL = os.getenv("WP_PUBLISH_WEBHOOK_URL", "").strip()
WP_PUBLISH_SECRET = os.getenv("WP_PUBLISH_SECRET", "").strip()
WP_RECIPE_CATEGORY_EN = os.getenv("WP_RECIPE_CATEGORY_EN", "Recipes").strip() or "Recipes"
WP_RECIPE_CATEGORY_FR = os.getenv("WP_RECIPE_CATEGORY_FR", "Recettes").strip() or "Recettes"
WP_RECIPE_CATEGORY_SLUG_EN = os.getenv("WP_RECIPE_CATEGORY_SLUG_EN", "recipes-recettes").strip()
WP_RECIPE_CATEGORY_SLUG_FR = os.getenv("WP_RECIPE_CATEGORY_SLUG_FR", "recipes-recettes-fr").strip()
ACF_RECIPE_SCHEMA_FIELDS = [s.strip() for s in os.getenv("ACF_RECIPE_SCHEMA_FIELDS", "recipe_schema_json").split(",") if s.strip()]

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "").strip()

# RSS Feeds
RSS_FEEDS = {
    "Google News El Mordjene": "https://news.google.com/rss/search?q=el+mordjene+OR+mordjane+OR+cebon+spread&hl=en-US&gl=US&ceid=US:en",
    "Google News Chocolate Trends": "https://news.google.com/rss/search?q=chocolate+trend+OR+filled+chocolate+bar+OR+pistachio+cream&hl=en-US&gl=US&ceid=US:en",
    "Google News Viral Desserts": "https://news.google.com/rss/search?q=viral+dessert+OR+viral+sweet+OR+tiktok+dessert&hl=en-US&gl=US&ceid=US:en",
    "Google News Confectionery": "https://news.google.com/rss/search?q=confectionery+news+OR+candy+industry+OR+chocolate+launch&hl=en-US&gl=US&ceid=US:en",
    "Google News Chocolate Spreads": "https://news.google.com/rss/search?q=chocolate+spread+OR+hazelnut+spread+OR+praline+spread&hl=en-US&gl=US&ceid=US:en",
    "Google News Bakery": "https://news.google.com/rss/search?q=bakery+trend+OR+pastry+trend+OR+dessert+shop&hl=en-US&gl=US&ceid=US:en",
    "Google News French Pastry": "https://news.google.com/rss/search?q=french+pastry+OR+viennoiserie+OR+patisserie+francaise&hl=en-US&gl=US&ceid=US:en",
    "Google News Algerian Food": "https://news.google.com/rss/search?q=recette+algerienne+OR+patisserie+algerienne+OR+dessert+algerien&hl=fr&gl=FR&ceid=FR:fr",
    "Google News North African Cuisine": "https://news.google.com/rss/search?q=north+african+dessert+OR+maghreb+cuisine+OR+algerian+sweets&hl=en-US&gl=US&ceid=US:en",
    "Google News Maghreb FR": "https://news.google.com/rss/search?q=maghreb+gourmand+OR+patisserie+maghrebine+OR+douceurs+orientales&hl=fr&gl=FR&ceid=FR:fr",
    "Google News Food Safety": "https://news.google.com/rss/search?q=food+recall+OR+ingredient+ban+OR+food+safety+alert+OR+chocolate+recall&hl=en-US&gl=US&ceid=US:en",
    "Google News Snack Launches": "https://news.google.com/rss/search?q=limited+edition+snack+OR+dessert+launch+OR+chocolate+launch&hl=en-US&gl=US&ceid=US:en",
    "Google News Gourmet Sweets": "https://news.google.com/rss/search?q=gourmet+dessert+OR+artisan+chocolate+OR+luxury+pastry&hl=en-US&gl=US&ceid=US:en",
}

YOUTUBE_SEARCH_QUERIES = [
    "el mordjene recipe",
    "homemade chocolate spread",
    "copycat pistachio chocolate bar",
    "french pastry recipe",
    "viennoiserie tutorial",
    "algerian dessert recipe",
    "north african sweets recipe",
    "makrout recipe",
    "qalb el louz recipe",
    "gourmet dessert recipe",
    "viral sweet recipe",
    "confectionery trend 2026",
]

BRAND_KEYWORDS = [
    "el mordjene", "el-mordjene", "mordjene", "mordjane",
    "cebon", "cebon spread", "cebon algeria",
]

CHOCOLATE_PRODUCT_KEYWORDS = [
    "chocolate spread", "hazelnut spread", "praline spread", "pistachio cream",
    "gianduja", "milk chocolate bar", "filled chocolate bar", "artisan chocolate",
    "gourmet chocolate", "chocolate truffles", "chocolate bark", "hot chocolate mix",
    "homemade chocolate", "chocolate recipe", "copycat chocolate", "dessert spread",
    "nutella alternative", "homemade nutella", "kinder bueno spread", "viral chocolate",
    "dubai chocolate", "dubai chocolate bar", "kunafa chocolate", "angel hair chocolate",
]

SWEETS_TREND_KEYWORDS = [
    "viral dessert", "viral sweet", "viral sweets", "viral recipe", "dessert trend",
    "bakery trend", "tiktok dessert", "tiktok sweets", "tiktok food trend",
    "easy dessert recipe", "no bake dessert", "3 ingredient dessert", "copycat recipe",
    "dupe recipe", "limited edition dessert", "dessert launch", "sweet snack",
    "candy making", "homemade candy", "candy recipe", "dessert cafe", "dessert shop",
]

FRENCH_CULINARY_KEYWORDS = [
    "french pastry", "french dessert", "patisserie francaise", "viennoiserie",
    "pain au chocolat", "croissant recipe", "madeleine", "mille feuille",
    "paris brest", "choux pastry", "tarte tatin", "entremet",
    "creme patissiere", "dessert francais", "bakery viennoiserie",
]

NORTH_AFRICAN_KEYWORDS = [
    "algerian dessert", "algerian recipe", "algerian food", "algerian pastry",
    "north african dessert", "north african food", "maghreb cuisine", "maghrebi sweets",
    "tamina", "tamina recipe", "makroud", "makrout", "maqrout", "qalb el louz",
    "kalb el louz", "zlabia", "griwech", "tcharek", "chamia", "cornes de gazelle",
    "recette algerienne", "patisserie algerienne", "douceurs orientales",
]

FOOD_NEWS_KEYWORDS = [
    "food recall", "chocolate recall", "food safety", "food additive", "ingredient ban",
    "banned ingredients", "fda ban", "banned snacks", "banned in europe",
    "confectionery news", "chocolate launch", "snack launch", "product launch",
    "retail availability", "where to buy", "price update", "limited edition snack",
]

HIGH_VALUE_KEYWORDS = [
    "viral", "trending", "limited edition", "copycat", "dupe", "recipe hack",
    "homemade", "artisan", "gourmet", "seasonal", "launch", "recall",
    "ingredients list", "nutrition facts", "where to buy", "price", "availability",
]

EXCLUDE_KEYWORDS = [
    "world cup", "fifa", "football", "soccer", "cricket",
    "ipl", "nba", "nfl", "baseball", "tennis", "f1",
    "premier league", "champions league", "rugby",
    "election", "congress", "senate", "parliament",
    "president biden", "president trump", "political",
    "cryptocurrency", "bitcoin", "ethereum", "stock market",
    "artificial intelligence", "machine learning",
    "movie review", "box office", "concert tour",
]

ALL_KEYWORDS = (
    BRAND_KEYWORDS
    + CHOCOLATE_PRODUCT_KEYWORDS
    + SWEETS_TREND_KEYWORDS
    + FRENCH_CULINARY_KEYWORDS
    + NORTH_AFRICAN_KEYWORDS
    + FOOD_NEWS_KEYWORDS
)

NEWSAPI_SEARCH_QUERIES = [
    "el mordjene",
    "chocolate spread trend",
    "hazelnut spread launch",
    "filled chocolate bar",
    "viral sweet",
    "dessert trend",
    "french pastry trend",
    "viennoiserie",
    "algerian dessert",
    "north african sweets",
    "confectionery news",
    "chocolate recall",
]

TRENDS_CORE_KEYWORDS = [
    "el mordjene",
    "chocolate spread",
    "hazelnut spread",
    "filled chocolate bar",
    "viral dessert",
    "viral sweet",
    "french pastry",
    "viennoiserie",
    "algerian dessert",
    "north african sweets",
    "makrout",
    "tamina recipe",
]

TRENDS_RELATED_TOPICS = [
    "el mordjene",
    "chocolate spread",
    "viral dessert",
    "french pastry",
    "algerian dessert",
]

SEASONAL_BOOSTS = {
    1: ["new year dessert", "winter chocolate", "comfort sweets"],
    2: ["valentine chocolate", "valentine dessert", "gift chocolate"],
    3: ["ramadan dessert", "ramadan sweets", "iftar dessert", "spring pastry"],
    4: ["eid dessert", "ramadan sweets", "easter chocolate", "spring dessert"],
    5: ["eid sweets", "mother's day dessert", "spring bakery"],
    6: ["summer dessert", "no bake dessert", "ice cream recipe", "frozen sweets"],
    7: ["summer sweets", "no bake dessert", "ice cream", "cold dessert"],
    8: ["back to school snack", "sweet snack", "easy treats"],
    9: ["fall dessert", "autumn baking", "bakery trend"],
    10: ["halloween candy", "spooky dessert", "pumpkin pastry"],
    11: ["holiday baking", "thanksgiving dessert", "gift chocolate"],
    12: ["christmas chocolate", "holiday dessert", "advent sweets", "gift chocolate"],
}

SPIKE_THRESHOLD = 1.8
SPIKE_MIN_SCORE = 30
ROLLING_WINDOW_HOURS = 24
SCAN_INTERVAL_MINUTES = 60
DEDUP_WINDOW_HOURS = 168

TRENDS_GEO = ""
TRENDS_KEYWORDS_PER_BATCH = 5
ENABLE_REALTIME_TRENDS = os.getenv("ENABLE_REALTIME_TRENDS", "true").lower() in ("true", "1", "yes")
TREND_DISCOVERY_MAX_QUERIES = int(os.getenv("TREND_DISCOVERY_MAX_QUERIES", "6"))
TREND_DISCOVERY_MAX_URLS = int(os.getenv("TREND_DISCOVERY_MAX_URLS", "12"))
NEWS_EXPANSION_DAYS = int(os.getenv("NEWS_EXPANSION_DAYS", "7"))

WP_DEFAULT_CATEGORY = "Blog"
WP_DEFAULT_STATUS = "draft"

ARTICLE_MIN_WORDS = 800
ARTICLE_MAX_WORDS = 1500
MIN_SOURCE_COUNT = int(os.getenv("MIN_SOURCE_COUNT", "2"))
MIN_UNIQUE_SOURCE_DOMAINS = int(os.getenv("MIN_UNIQUE_SOURCE_DOMAINS", "2"))
BLOCK_SOURCELESS_NON_RECIPE = os.getenv("BLOCK_SOURCELESS_NON_RECIPE", "true").lower() in ("true", "1", "yes")
REQUIRE_TRUSTED_SOURCE_FOR_NEWS = os.getenv("REQUIRE_TRUSTED_SOURCE_FOR_NEWS", "true").lower() in ("true", "1", "yes")
GEMINI_MODEL = "gemini-2.5-flash"
SKIP_AI_IMAGE = os.getenv("SKIP_AI_IMAGE", "false").lower() in ("true", "1", "yes")
USE_GEMINI_IMAGEN = os.getenv("USE_GEMINI_IMAGEN", "false").lower() in ("true", "1", "yes")

CHECK_EXISTING_CONTENT = True
EXISTING_CONTENT_CHECK_LIMIT = 50
DUPLICATE_SIMILARITY_THRESHOLD = 0.4
RECENT_TOPIC_REPEAT_WINDOW = 12
RECENT_TOPIC_REPEAT_PENALTY = 12

LOG_FILE = "agent.log"
LOG_LEVEL = "INFO"

