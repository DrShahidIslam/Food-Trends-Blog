"""
Article Generator  Uses Gemini to write SEO-optimized articles
from source material gathered by the source fetcher.
"""
import json
import logging
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import config
from gemini_client import generate_content_with_fallback
from writer.seo_prompt import build_article_prompt
from writer.source_fetcher import fetch_multiple_sources, analyze_source_collection

logger = logging.getLogger(__name__)

RECIPE_ACF_KEYS = {
    "recipe_name",
    "recipe_description",
    "recipe_yield",
    "prep_time_minutes",
    "cook_time_minutes",
    "total_time_minutes",
    "ingredients",
    "instructions",
    "recipe_image",
    "nutrition_calories",
    "video_url",
    "author_name",
    "recipe_keywords",
    "recipecuisine",
    "recipecategory",
    "video_upload_date",
}

RECIPE_KEY_ALIASES = {
    "recipe_title": "recipe_name",
    "name": "recipe_name",
    "title": "recipe_name",
    "nom": "recipe_name",
    "nom_recette": "recipe_name",
    "description": "recipe_description",
    "recipe_summary": "recipe_description",
    "summary": "recipe_description",
    "resume": "recipe_description",
    "description_recette": "recipe_description",
    "yield": "recipe_yield",
    "servings": "recipe_yield",
    "portions": "recipe_yield",
    "prep_time": "prep_time_minutes",
    "temps_preparation": "prep_time_minutes",
    "cook_time": "cook_time_minutes",
    "temps_cuisson": "cook_time_minutes",
    "total_time": "total_time_minutes",
    "temps_total": "total_time_minutes",
    "recipe_cuisine": "recipecuisine",
    "recipe_category": "recipecategory",
    "cuisine": "recipecuisine",
    "categorie": "recipecategory",
    "keywords": "recipe_keywords",
    "mots_cles": "recipe_keywords",
    "calories": "nutrition_calories",
    "image": "recipe_image",
    "image_url": "recipe_image",
    "video": "video_url",
    "video_date": "video_upload_date",
    "video_upload": "video_upload_date",
    "auteur": "author_name",
    "etapes": "instructions",
}

RECIPE_CATEGORY_NAMES = {"recipes", "recettes"}
RECIPE_TITLE_MARKERS = [
    "recipe",
    "recette",
    "how to make",
    "comment faire",
    "copycat",
    "homemade",
    "fait maison",
    "ingredients",
    "ingr\u00e9dients",
    "instructions",
]
INGREDIENT_SECTION_NAMES = ["Ingredients", "Ingredients List", "Ingr\u00e9dients"]
INSTRUCTION_SECTION_NAMES = ["Instructions", "Method", "Directions", "Preparation", "Pr\u00e9paration", "\u00c9tapes", "Etapes"]
INGREDIENT_STOP_NAMES = [
    "Equipment",
    "Instructions",
    "Method",
    "Directions",
    "Preparation",
    "Pr\u00e9paration",
    "\u00c9tapes",
    "Etapes",
    "Practical Tips",
    "Conseils pratiques",
    "Outlook",
    "Frequently Asked Questions",
    "Questions fr\u00e9quentes",
    "FAQ",
    "Post Tags",
]
INSTRUCTION_STOP_NAMES = [
    "Practical Tips",
    "Conseils pratiques",
    "Outlook",
    "Enjoy",
    "Frequently Asked Questions",
    "Questions fr\u00e9quentes",
    "FAQ",
    "Post Tags",
]


def _infer_intent(topic):
    """Infer content intent for better prompt shaping."""
    txt = f"{topic.get('topic', '')} {topic.get('matched_keyword', '')}".lower()

    if any(k in txt for k in ["recipe", "how to", "homemade", "ingredients", "make "]):
        return "recipe"
    if any(k in txt for k in ["where to buy", "buy", "price", "availability", "store", "amazon"]):
        return "buyer"
    if any(k in txt for k in ["ban", "recall", "news", "update", "lawsuit"]):
        return "news"
    if any(k in txt for k in ["viral", "tiktok"]):
        return "trend"
    return "explainer"


def _normalize_writing_topic(topic_title):
    topic_title = (topic_title or "").strip()
    if topic_title.lower().startswith("rising search:"):
        return topic_title.split(":", 1)[1].strip()
    return topic_title


def _build_topic_expansion_queries(topic, intent):
    base_topic = _normalize_writing_topic(topic.get("topic", ""))
    matched_keyword = (topic.get("matched_keyword") or "").strip()
    story_titles = [(s.get("title") or "").strip() for s in (topic.get("stories") or [])[:4]]

    candidates = []
    for value in [matched_keyword, base_topic, *story_titles]:
        value = value.strip()
        if value and value not in candidates:
            candidates.append(value)

    expanded = []
    for value in candidates:
        expanded.append(value)
        if intent == "recipe":
            expanded.extend([
                f"{value} recipe",
                f"{value} ingredients",
                f"how to make {value}",
            ])
        elif intent == "buyer":
            expanded.extend([
                f"{value} where to buy",
                f"{value} price",
                f"{value} availability",
            ])
        elif intent == "news":
            expanded.extend([
                f"{value} official statement",
                f"{value} recall",
                f"{value} update",
            ])
        else:
            expanded.extend([
                f"{value} ingredients",
                f"{value} recipe",
                f"{value} guide",
                f"{value} review",
            ])

    deduped = []
    seen = set()
    limit = int(getattr(config, "TREND_DISCOVERY_MAX_QUERIES", 6))
    for query in expanded:
        key = query.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(query.strip())
        if len(deduped) >= limit:
            break
    return deduped


def _search_news_for_trend(keyword, days=None):
    """Search Google News RSS and NewsAPI to find background context for a topic."""
    urls = []
    days = int(days or getattr(config, "NEWS_EXPANSION_DAYS", 7))

    try:
        import feedparser
        import urllib.parse

        encoded_kw = urllib.parse.quote(keyword)
        rss_url = f"https://news.google.com/rss/search?q={encoded_kw}&hl=en-US&gl=US&ceid=US:en"
        feed = feedparser.parse(rss_url)
        for entry in feed.entries[:6]:
            if entry.link and entry.link not in urls:
                urls.append(entry.link)
    except Exception as e:
        logger.warning(f"Failed to fetch Google News RSS for trend: {e}")

    if config.NEWS_API_KEY:
        try:
            from datetime import datetime, timedelta
            from newsapi import NewsApiClient

            newsapi = NewsApiClient(api_key=config.NEWS_API_KEY)
            from_date = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")
            results = newsapi.get_everything(
                q=keyword,
                language="en",
                sort_by="relevancy",
                from_param=from_date,
                page_size=8,
            )
            if results.get("status") == "ok":
                for article in results.get("articles", [])[:6]:
                    url = article.get("url")
                    if url and url not in urls:
                        urls.append(url)
        except Exception as e:
            logger.warning(f"Failed to fetch NewsAPI for trend: {e}")

    return urls


def _discover_supporting_urls(topic, intent, source_urls):
    """Expand thin alerts into richer source sets before generation."""
    discovered = []
    seen = set(u for u in source_urls if u)
    queries = _build_topic_expansion_queries(topic, intent)

    for query in queries:
        try:
            found_urls = _search_news_for_trend(query)
        except Exception as e:
            logger.warning(f"Failed query expansion for '{query}': {e}")
            continue

        for url in found_urls:
            if url and url not in seen:
                seen.add(url)
                discovered.append(url)
        if len(discovered) >= int(getattr(config, "TREND_DISCOVERY_MAX_URLS", 12)):
            break

    if discovered:
        logger.info(f"   Expanded topic research with {len(discovered)} supporting URLs across {len(queries)} query variants.")
    return discovered


def _extract_faqpage_json(text):
    """Extract raw FAQPage JSON-LD from text using brace matching."""
    script_match = re.search(
        r'<script\s+type=["\']application/ld\+json["\']\s*>(.*?)</script>',
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )
    if script_match:
        json_str = script_match.group(1).strip()
        if '"FAQPage"' in json_str or "'FAQPage'" in json_str:
            return json_str

    match = re.search(r'\{\s*["\']@context["\']', text)
    if not match:
        return None

    start = match.start()
    depth = 0
    in_string = False
    escape = False
    quote = None
    i = start
    while i < len(text):
        c = text[i]
        if escape:
            escape = False
            i += 1
            continue
        if c == '\\' and in_string:
            escape = True
            i += 1
            continue
        if in_string:
            if c == quote:
                in_string = False
            i += 1
            continue
        if c in ('"', "'"):
            in_string = True
            quote = c
            i += 1
            continue
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                return text[start:i + 1].strip()
        i += 1
    return None


def _strip_faq_and_schema_from_content(content):
    """Remove FAQ section and JSON-LD schema if the model wrongly put them inside CONTENT."""
    if not content:
        return content
    while True:
        json_str = _extract_faqpage_json(content)
        if not json_str:
            break
        content = content.replace(json_str, "", 1).strip()
    content = re.sub(
        r'<script\s+type=["\']application/ld\+json["\']\s*>.*?</script>\s*',
        '',
        content,
        flags=re.DOTALL | re.IGNORECASE,
    )
    content = re.sub(r'\n{3,}', '\n\n', content).strip()
    return content


def _downgrade_h1_tags(content):
    """Ensure the article body does not contain an H1 because WordPress title is already the H1."""
    if not content:
        return content
    content = re.sub(r'<h1(\b[^>]*)?>', lambda m: f"<h2{m.group(1) or ''}>", content, flags=re.IGNORECASE)
    content = re.sub(r'</h1>', '</h2>', content, flags=re.IGNORECASE)
    return content


def _strip_code_fences(text):
    if not text:
        return text
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:].strip()
    elif text.startswith("```"):
        text = text[3:].strip()
    if text.endswith("```"):
        text = text[:-3].strip()
    return text


def _canonical_recipe_key(key):
    normalized = re.sub(r'[^a-z0-9]+', '_', str(key).strip().lower()).strip('_')
    if normalized in RECIPE_ACF_KEYS:
        return normalized
    return RECIPE_KEY_ALIASES.get(normalized, normalized)


def _parse_minutes(value):
    if value in (None, ""):
        return ""
    if isinstance(value, (int, float)):
        return int(value)
    match = re.search(r'\d+', str(value))
    return int(match.group(0)) if match else ""


def _normalize_multiline_value(value):
    if value in (None, ""):
        return ""
    if isinstance(value, list):
        lines = []
        for item in value:
            item_text = str(item).strip()
            if item_text:
                lines.append(item_text)
        return "\n".join(lines)
    return str(value).strip()


def _normalize_recipe_fields(recipe_data):
    if not isinstance(recipe_data, dict):
        return {}

    normalized = {key: "" for key in RECIPE_ACF_KEYS}
    for raw_key, raw_value in recipe_data.items():
        key = _canonical_recipe_key(raw_key)
        if key not in RECIPE_ACF_KEYS:
            continue
        if key in {"ingredients", "instructions"}:
            normalized[key] = _normalize_multiline_value(raw_value)
        elif key in {"prep_time_minutes", "cook_time_minutes", "total_time_minutes"}:
            normalized[key] = _parse_minutes(raw_value)
        else:
            normalized[key] = str(raw_value).strip() if raw_value is not None else ""

    return {key: value for key, value in normalized.items() if value not in (None, "")}



def _merge_recipe_fields(*field_sets):
    merged = {}
    for field_set in field_sets:
        if not isinstance(field_set, dict):
            continue
        for key, value in field_set.items():
            if value not in (None, ""):
                merged[key] = value
    return merged

def _minutes_to_iso(value):
    if value in (None, ""):
        return ""
    try:
        minutes = int(value)
    except (TypeError, ValueError):
        return ""
    if minutes <= 0:
        return ""
    return f"PT{minutes}M"


def _split_lines(value):
    if value in (None, ""):
        return []
    lines = []
    for raw_line in str(value).splitlines():
        line = raw_line.strip()
        if line:
            lines.append(line)
    return lines


def _is_url(value):
    if not value:
        return False
    val = str(value).strip().lower()
    return val.startswith("http://") or val.startswith("https://")


def _build_recipe_schema_from_acf(article):
    acf_fields = article.get("acf_fields", {}) or {}
    recipe_name = (acf_fields.get("recipe_name") or article.get("title", "")).strip()
    ingredients = _split_lines(acf_fields.get("ingredients"))
    instructions = _split_lines(acf_fields.get("instructions"))
    if not recipe_name or not ingredients or not instructions:
        return {}

    schema = {
        "@context": "https://schema.org",
        "@type": "Recipe",
        "name": recipe_name,
    }

    description = (acf_fields.get("recipe_description") or "").strip()
    if description:
        schema["description"] = description

    recipe_yield = (acf_fields.get("recipe_yield") or "").strip()
    if recipe_yield:
        schema["recipeYield"] = recipe_yield

    prep_time = _minutes_to_iso(acf_fields.get("prep_time_minutes"))
    cook_time = _minutes_to_iso(acf_fields.get("cook_time_minutes"))
    total_time = _minutes_to_iso(acf_fields.get("total_time_minutes"))
    if prep_time:
        schema["prepTime"] = prep_time
    if cook_time:
        schema["cookTime"] = cook_time
    if total_time:
        schema["totalTime"] = total_time

    schema["recipeIngredient"] = ingredients
    schema["recipeInstructions"] = [
        {"@type": "HowToStep", "text": step}
        for step in instructions
    ]

    recipe_keywords = (acf_fields.get("recipe_keywords") or "").strip()
    if recipe_keywords:
        schema["keywords"] = recipe_keywords

    recipe_cuisine = (acf_fields.get("recipecuisine") or "").strip()
    if recipe_cuisine:
        schema["recipeCuisine"] = recipe_cuisine

    recipe_category = (acf_fields.get("recipecategory") or "").strip()
    if recipe_category:
        schema["recipeCategory"] = recipe_category

    author_name = (acf_fields.get("author_name") or "").strip()
    if author_name:
        schema["author"] = {"@type": "Person", "name": author_name}

    nutrition_calories = (acf_fields.get("nutrition_calories") or "").strip()
    if nutrition_calories:
        schema["nutrition"] = {
            "@type": "NutritionInformation",
            "calories": nutrition_calories,
        }

    image_value = acf_fields.get("recipe_image")
    if _is_url(image_value):
        schema["image"] = [str(image_value).strip()]

    video_url = (acf_fields.get("video_url") or "").strip()
    if video_url:
        video_obj = {"@type": "VideoObject", "contentUrl": video_url}
        upload_date = (acf_fields.get("video_upload_date") or "").strip()
        if upload_date:
            video_obj["uploadDate"] = upload_date
        schema["video"] = video_obj

    return schema


def _attach_recipe_schema_fields(article):
    fields = getattr(config, "ACF_RECIPE_SCHEMA_FIELDS", []) or []
    if isinstance(fields, str):
        fields = [fields]
    fields = [field for field in fields if field]
    if not fields:
        return

    schema = _build_recipe_schema_from_acf(article)
    if not schema:
        return

    schema_json = json.dumps(schema, ensure_ascii=True)
    acf_fields = article.setdefault("acf_fields", {})
    for field in fields:
        acf_fields[field] = schema_json


def _content_has_recipe_structure(content):
    text = _content_to_line_text(content)
    if not text:
        return False

    has_ingredients = bool(re.search(r'(?im)^(ingredients|ingredients list|ingr\u00e9dients)\s*:?\s*$', text))
    has_instructions = bool(re.search(r'(?im)^(instructions|method|directions|preparation|pr\u00e9paration|\u00e9tapes|etapes)\s*:?\s*$', text))
    return has_ingredients and has_instructions

def _is_recipe_article(result, intent=None):
    if (intent or "").lower() == "recipe":
        return True
    category = str(result.get("category", "")).strip().lower()
    slug = str(result.get("slug", "")).strip().lower()
    title = str(result.get("title", "")).strip().lower()
    tags = " ".join(result.get("tags", [])).lower()
    acf_fields = result.get("acf_fields", {}) or {}
    content = result.get("content", "") or result.get("full_content", "")

    return (
        category in RECIPE_CATEGORY_NAMES
        or "recipe" in slug
        or "recette" in slug
        or any(marker in title for marker in RECIPE_TITLE_MARKERS)
        or any(marker in tags for marker in RECIPE_TITLE_MARKERS)
        or bool(acf_fields.get("ingredients") or acf_fields.get("instructions"))
        or _content_has_recipe_structure(content)
    )

def _recipe_fields_complete(acf_fields):
    if not isinstance(acf_fields, dict):
        return False
    return bool(
        acf_fields.get("recipe_name")
        and acf_fields.get("recipe_description")
        and acf_fields.get("ingredients")
        and acf_fields.get("instructions")
    )


def _build_recipe_extraction_prompt(article):
    return f"""Extract recipe data from the article below and return only one raw JSON object with these exact keys:
recipe_name
recipe_description
recipe_yield
prep_time_minutes
cook_time_minutes
total_time_minutes
ingredients
instructions
recipe_image
nutrition_calories
video_url
author_name
recipe_keywords
recipecuisine
recipecategory
video_upload_date

Rules:
- No markdown fences.
- ingredients must be one ingredient per line in a single string.
- instructions must be one step per line in a single string.
- Use empty string for unknown optional values.
- prep_time_minutes, cook_time_minutes, and total_time_minutes must be numeric when known, otherwise empty string.
- Do not invent facts that are not in the article.

TITLE: {article.get('title', '')}
CATEGORY: {article.get('category', '')}
LANGUAGE: {article.get('language', 'en')}

ARTICLE:
{article.get('content', '')}
"""


def _extract_recipe_fields_via_fallback(article):
    try:
        prompt = _build_recipe_extraction_prompt(article)
        response = generate_content_with_fallback(
            model=config.GEMINI_MODEL,
            contents=prompt,
        )
        recipe_json = _strip_code_fences(response.text)
        recipe_data = json.loads(recipe_json)
        normalized = _normalize_recipe_fields(recipe_data)
        if normalized:
            logger.info("   Recovered recipe ACF fields via fallback extraction")
        return normalized
    except Exception as e:
        logger.warning(f"   Failed fallback recipe extraction: {e}")
        return {}


def _strip_html_tags(html):
    if not html:
        return ""
    text = re.sub(r'<script\b[^>]*>.*?</script>', ' ', html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<style\b[^>]*>.*?</style>', ' ', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<[^>]+>', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()


def _extract_intro_text(content, max_words=120):
    plain = _strip_html_tags(content)
    if not plain:
        return ""
    words = plain.split()
    return " ".join(words[:max_words]).strip()


def _extract_heading_texts(content):
    if not content:
        return []
    headings = re.findall(r'<h[2-3][^>]*>(.*?)</h[2-3]>', content, flags=re.IGNORECASE | re.DOTALL)
    return [_strip_html_tags(item).strip() for item in headings if _strip_html_tags(item).strip()]


def _keyword_in_text(keyword, text):
    keyword = (keyword or '').strip().lower()
    text = (text or '').strip().lower()
    if not keyword or not text:
        return False
    return keyword in text


def _compute_keyword_density(keyword, content):
    keyword = (keyword or '').strip().lower()
    plain = _strip_html_tags(content).lower()
    if not keyword or not plain:
        return 0.0
    words = re.findall(r'\b\w+\b', plain)
    if not words:
        return 0.0
    occurrences = plain.count(keyword)
    return round((occurrences / len(words)) * 100, 2)


def _build_generation_checks(article, primary_keyword):
    focus_keyword = (primary_keyword or article.get('title', '')).strip()
    title = article.get('title', '')
    meta = article.get('meta_description', '')
    slug = article.get('slug', '')
    content = article.get('content', '')
    intro = _extract_intro_text(content)
    headings = _extract_heading_texts(content)
    density = _compute_keyword_density(focus_keyword, content)

    checks = {
        'focus_keyword': focus_keyword,
        'title_has_keyword': _keyword_in_text(focus_keyword, title),
        'meta_has_keyword': _keyword_in_text(focus_keyword, meta),
        'slug_has_keyword': _keyword_in_text(focus_keyword.replace(' ', '-'), slug),
        'intro_has_keyword': _keyword_in_text(focus_keyword, intro),
        'has_h2_or_h3': bool(headings),
        'h2_has_keyword': any(_keyword_in_text(focus_keyword, heading) for heading in headings),
        'title_length': len(title),
        'meta_length': len(meta),
        'keyword_density_percent': density,
    }

    warnings = []
    if focus_keyword and not checks['title_has_keyword']:
        warnings.append('Title is missing the focus keyword.')
    if focus_keyword and not checks['meta_has_keyword']:
        warnings.append('Meta description is missing the focus keyword.')
    if focus_keyword and not checks['slug_has_keyword']:
        warnings.append('Slug does not reflect the focus keyword.')
    if focus_keyword and not checks['intro_has_keyword']:
        warnings.append('Opening section does not mention the focus keyword early enough.')
    if not checks['has_h2_or_h3']:
        warnings.append('Article body is missing structured subheadings.')
    elif focus_keyword and not checks['h2_has_keyword']:
        warnings.append('No subheading includes the focus keyword.')
    if checks['title_length'] > 60:
        warnings.append('Title is longer than 60 characters.')
    if checks['meta_length'] < 140 or checks['meta_length'] > 160:
        warnings.append('Meta description is outside the 140-160 character target.')
    if density == 0:
        warnings.append('Focus keyword does not appear in the article body.')
    elif density > 1.5:
        warnings.append('Focus keyword density may be too high.')

    plain = _strip_html_tags(content).lower()
    banned_phrases = [
        "people are searching for",
        "is trending on google",
        "trending on google",
        "search volume",
        "rising search",
        "google trends shows",
    ]
    for phrase in banned_phrases:
        if phrase in plain:
            warnings.append('Article discusses search popularity instead of user-facing topic value.')
            break

    checks['warnings'] = warnings
    return checks


def _build_policy_checks(article, topic, source_texts, intent, used_summary_fallback=False):
    quality = analyze_source_collection(source_texts)
    words = int(article.get("word_count") or len((article.get("content") or "").split()))
    flags = []
    warnings = []

    if used_summary_fallback:
        flags.append("summary_only_fallback")
        warnings.append("Article was generated from topic summaries instead of extracted source pages.")

    if quality["source_count"] < max(1, int(getattr(config, "MIN_SOURCE_COUNT", 2))):
        flags.append("low_source_count")
        warnings.append(f"Only {quality['source_count']} extracted source(s) were available.")

    if quality["unique_domain_count"] < max(1, int(getattr(config, "MIN_UNIQUE_SOURCE_DOMAINS", 2))):
        flags.append("low_source_diversity")
        warnings.append(f"Only {quality['unique_domain_count']} unique source domain(s) were used.")

    if words < int(getattr(config, "ARTICLE_MIN_WORDS", 800)):
        flags.append("thin_content")
        warnings.append(f"Article is shorter than the configured minimum ({words} words).")

    needs_trusted = intent in {"news", "trend", "buyer"}
    if needs_trusted and getattr(config, "REQUIRE_TRUSTED_SOURCE_FOR_NEWS", True) and quality["trusted_unique_count"] < 1:
        flags.append("no_trusted_source")
        warnings.append("No trusted or authoritative source domain was found for a news/trend/buyer article.")

    block_publish = any(flag in flags for flag in {"summary_only_fallback", "low_source_count", "low_source_diversity", "no_trusted_source"})

    return {
        "source_quality": quality,
        "flags": flags,
        "warnings": warnings,
        "intent": intent,
        "block_publish": block_publish,
        "topic": topic.get("topic", ""),
    }


def _content_to_line_text(content):
    if not content:
        return ""
    text = re.sub(r'(?i)<br\s*/?>', "\n", content)
    text = re.sub(r'(?i)</(p|div|li|ul|ol|h2|h3|h4|h5|h6|section)>', "\n", text)
    text = re.sub(r'(?i)<li[^>]*>', "- ", text)
    text = re.sub(r'<[^>]+>', '', text)
    text = text.replace('&nbsp;', ' ')
    text = re.sub(r'\r\n?', '\n', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def _extract_named_section(text, section_names, stop_names):
    if not text:
        return ""
    start_pattern = "|".join(re.escape(name) for name in section_names)
    stop_pattern = "|".join(re.escape(name) for name in stop_names)
    pattern = rf'(?ims)^(?:{start_pattern})\s*:?\s*\n(.+?)(?=^(?:{stop_pattern})\s*:?[ \t]*$|\Z)'
    match = re.search(pattern, text)
    return match.group(1).strip() if match else ""


def _normalize_recipe_lines(section_text):
    if not section_text:
        return ""
    lines = []
    for raw_line in section_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        line = re.sub("^(?:[-*\\u2022]+|\\d+[\\.)])\\s*", '', line).strip()
        if line:
            lines.append(line)
    return "\n".join(lines)


def _extract_recipe_description(content):
    plain = _strip_html_tags(content)
    if not plain:
        return ""
    sentences = re.split(r'(?<=[.!?])\s+', plain)
    return " ".join(sentence.strip() for sentence in sentences[:2] if sentence.strip())[:300].strip()


def _extract_recipe_fields_from_article(article):
    content = article.get('content', '')
    text = _content_to_line_text(content)
    ingredients_block = _extract_named_section(
        text,
        INGREDIENT_SECTION_NAMES,
        INGREDIENT_STOP_NAMES,
    )
    instructions_block = _extract_named_section(
        text,
        INSTRUCTION_SECTION_NAMES,
        INSTRUCTION_STOP_NAMES,
    )

    ingredients = _normalize_recipe_lines(ingredients_block)
    instructions = _normalize_recipe_lines(instructions_block)
    if not ingredients or not instructions:
        return {}

    recipe_name = article.get('title', '').strip()
    fallback = {
        'recipe_name': recipe_name,
        'recipe_description': _extract_recipe_description(content),
        'ingredients': ingredients,
        'instructions': instructions,
        'recipe_yield': '4 servings',
        'recipe_keywords': ", ".join(article.get('tags', [])) if article.get('tags') else article.get('slug', '').replace('-', ', '),
        'recipecategory': 'Dessert',
        'recipecuisine': 'International',
        'author_name': 'El Mordjene Team',
    }
    return _normalize_recipe_fields(fallback)


def _parse_article_output(raw_text, intent=None):
    """Parse the structured output from Gemini into article components."""
    try:
        result = {}

        title_match = re.search(r'TITLE:\s*(.+?)(?:\n|META_DESCRIPTION:)', raw_text, re.DOTALL)
        result["title"] = title_match.group(1).strip() if title_match else ""

        meta_match = re.search(r'META_DESCRIPTION:\s*(.+?)(?:\n|SLUG:)', raw_text, re.DOTALL)
        result["meta_description"] = meta_match.group(1).strip() if meta_match else ""

        slug_match = re.search(r'SLUG:\s*(.+?)(?:\n|TAGS:)', raw_text, re.DOTALL)
        result["slug"] = slug_match.group(1).strip() if slug_match else ""

        tags_match = re.search(r'TAGS:\s*(.+?)(?:\n|CATEGORY:)', raw_text, re.DOTALL)
        if tags_match:
            tags_raw = tags_match.group(1).strip()
            result["tags"] = [t.strip() for t in tags_raw.split(",") if t.strip()]
        else:
            result["tags"] = []

        cat_match = re.search(r'CATEGORY:\s*(.+?)(?:\n|LANGUAGE:)', raw_text, re.DOTALL)
        result["category"] = cat_match.group(1).strip() if cat_match else "Recipes"

        lang_match = re.search(r'LANGUAGE:\s*(en|fr)(?:\n|---)', raw_text, re.IGNORECASE | re.DOTALL)
        result["language"] = lang_match.group(1).strip().lower() if lang_match else "en"

        content_match = re.search(r'---CONTENT_START---(.*?)---CONTENT_END---', raw_text, re.DOTALL)
        content = content_match.group(1).strip() if content_match else ""

        schema_json = _extract_faqpage_json(content)
        content = _strip_faq_and_schema_from_content(content)
        content = _downgrade_h1_tags(content)
        if schema_json:
            schema_block = (
                '<!-- wp:html -->\n'
                '<script type="application/ld+json">\n'
                + schema_json
                + '\n</script>\n'
                '<!-- /wp:html -->'
            )
            content = content.strip() + "\n\n" + schema_block

        result["content"] = content
        result["full_content"] = content
        result["faq_html"] = ""

        recipe_match = re.search(r'---RECIPE_DATA_START---\s*(.*?)\s*---RECIPE_DATA_END---', raw_text, re.DOTALL)
        result["acf_fields"] = {}
        if recipe_match:
            recipe_json_str = _strip_code_fences(recipe_match.group(1).strip())
            try:
                recipe_data = json.loads(recipe_json_str)
                result["acf_fields"] = _normalize_recipe_fields(recipe_data)
                if result["acf_fields"]:
                    logger.info(f"   Parsed ACF recipe fields: {list(result['acf_fields'].keys())}")
            except Exception as e:
                logger.warning(f"   Failed to parse RECIPE_DATA JSON: {e}")

        recipe_like = _is_recipe_article(result, intent=intent)
        if recipe_like and result.get("category", "").strip().lower() not in RECIPE_CATEGORY_NAMES:
            normalized_category = config.WP_RECIPE_CATEGORY_FR if result.get("language") == "fr" else config.WP_RECIPE_CATEGORY_EN
            logger.info(f"   Recipe structure detected; normalizing category to {normalized_category}")
            result["category"] = normalized_category

        if not result["title"] or not result["content"]:
            logger.warning("Missing essential fields, attempting raw extraction...")
            if not result["title"]:
                first_line = raw_text.strip().split("\n")[0]
                result["title"] = re.sub(r'^#+\s*', '', first_line)[:60]
            if not result["content"]:
                result["content"] = _downgrade_h1_tags(raw_text)
                result["full_content"] = result["content"]

        if recipe_like and not _recipe_fields_complete(result["acf_fields"]):
            fallback_fields = _extract_recipe_fields_via_fallback(result)
            if fallback_fields:
                result["acf_fields"] = _merge_recipe_fields(result["acf_fields"], fallback_fields)

        if recipe_like and not _recipe_fields_complete(result["acf_fields"]):
            deterministic_fields = _extract_recipe_fields_from_article(result)
            if deterministic_fields:
                logger.info("   Recovered recipe ACF fields from article body structure")
                result["acf_fields"] = _merge_recipe_fields(result.get("acf_fields", {}), deterministic_fields)
        if recipe_like:
            default_fields = {
                "recipe_name": result.get("title", "").strip(),
                "recipe_description": _extract_recipe_description(result.get("content", "")),
                "recipe_keywords": ", ".join(result.get("tags", [])) if result.get("tags") else result.get("slug", "").replace("-", ", "),
                "recipecategory": "Dessert",
                "recipecuisine": "Algerian" if result.get("language") == "fr" else "International",
                "author_name": "El Mordjene Team",
            }
            result["acf_fields"] = _merge_recipe_fields(result.get("acf_fields", {}), _normalize_recipe_fields(default_fields))
            _attach_recipe_schema_fields(result)
            acf_keys = sorted((result.get("acf_fields") or {}).keys())
            logger.info(f"   Recipe article detected with ACF keys: {acf_keys}")

        return result

    except Exception as e:
        logger.error(f"Parse error: {e}")
        return None


def generate_article(topic, source_urls=None):
    """
    Generate a complete SEO-optimized article for a trending topic.
    """
    logger.info(f" Generating article for: {topic.get('topic', 'Unknown')}")

    topic["topic"] = _normalize_writing_topic(topic.get("topic", ""))

    if source_urls is None:
        source_urls = []
        for story in topic.get("stories", []):
            url = story.get("url", "")
            if url and url.startswith("http"):
                source_urls.append(url)

    top_url = topic.get("top_url", "")
    if top_url and top_url not in source_urls:
        source_urls.insert(0, top_url)

    intent = _infer_intent(topic)
    source_urls.extend(_discover_supporting_urls(topic, intent, source_urls))
    deduped_source_urls = []
    seen_source_urls = set()
    for url in source_urls:
        if url and url not in seen_source_urls:
            seen_source_urls.add(url)
            deduped_source_urls.append(url)
    source_urls = deduped_source_urls

    logger.info(f"  Fetching {len(source_urls)} source URLs...")
    source_texts = fetch_multiple_sources(source_urls, max_sources=8)

    used_summary_fallback = False
    if not source_texts:
        if intent != "recipe" and getattr(config, "BLOCK_SOURCELESS_NON_RECIPE", True):
            raise ValueError("No extractable sources were found, so generation was skipped to avoid weak AI-only content.")
        logger.warning("   No source material could be extracted. Using topic summary only.")
        source_texts = [{
            "title": topic.get("topic", ""),
            "text": "\n".join(s.get("summary", "") for s in topic.get("stories", [])),
            "source_domain": "aggregated_summaries",
            "url": "",
        }]
        used_summary_fallback = True

    prompt = build_article_prompt(
        topic_title=topic.get("topic", "Food & Recipe Update"),
        source_texts=source_texts,
        matched_keyword=topic.get("matched_keyword", ""),
        intent=intent,
    )

    try:
        logger.info("   Calling Gemini API...")
        response = generate_content_with_fallback(
            model=config.GEMINI_MODEL,
            contents=prompt,
        )
        raw_output = response.text
        logger.info(f"   Gemini responded ({len(raw_output)} chars)")

    except Exception as e:
        logger.error(f"   Gemini API error: {e}")
        return None

    article = _parse_article_output(raw_output, intent=intent)

    if article:
        article["intent"] = intent
        article["sources_used"] = [s.get("source_domain", "") for s in source_texts]
        article["word_count"] = len(article.get("content", "").split())
        article["generation_checks"] = _build_generation_checks(
            article,
            topic.get("matched_keyword", "") or topic.get("topic", ""),
        )
        article["policy_checks"] = _build_policy_checks(
            article,
            topic,
            source_texts,
            intent,
            used_summary_fallback=used_summary_fallback,
        )
        for warning in article["generation_checks"].get("warnings", []):
            logger.warning(f"   Content quality warning: {warning}")
        for warning in article["policy_checks"].get("warnings", []):
            logger.warning(f"   Policy-risk warning: {warning}")
        logger.info(f"   Article generated: '{article['title']}' ({article['word_count']} words)")
    else:
        logger.error("   Failed to parse Gemini output")

    return article








