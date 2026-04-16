"""
SEO Prompt Template - Master prompt for Gemini article generation.
Tailored for el-mordjene.info: food, recipes, chocolate, desserts, spreads.
"""
import hashlib

import json
import os

# Base directory
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
PUBLISHED_POSTS_PATH = os.path.join(BASE_DIR, "published_posts.json")

def _load_internal_links():
    try:
        with open(PUBLISHED_POSTS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

INTERNAL_LINKS = _load_internal_links()

def _pick_layout_variant(topic_title, matched_keyword):
    variants = [
        {
            "name": "Explainer and Practical Steps",
            "outline": [
                "Start with the key question users ask now",
                "Explain what changed and why the topic matters",
                "Give practical steps readers can follow",
                "Add common mistakes and fixes",
                "Close with a concise FAQ section",
            ],
        },
        {
            "name": "Myth vs Fact and Action Plan",
            "outline": [
                "Summarize what is confirmed vs uncertain",
                "Add a myth-vs-fact evidence section",
                "Provide a do-this-next checklist",
                "Cover substitutions and alternatives",
                "Close with transactional FAQ questions",
            ],
        },
        {
            "name": "Chooser Guide",
            "outline": [
                "Define user intent and decision criteria",
                "Compare options by quality, price, and availability",
                "Highlight warning signs and authenticity checks",
                "Explain who should choose which option",
                "Close with FAQ answers to buying concerns",
            ],
        },
        {
            "name": "Trend Analysis and Regional Context",
            "outline": [
                "Describe why this trend accelerated",
                "Compare US, EU, FR, or DZ angles when relevant",
                "Explain social media influence",
                "Add likely 30-90 day outlook",
                "Close with short direct FAQ answers",
            ],
        },
    ]

    seed = f"{topic_title}|{matched_keyword}".strip().lower()
    idx = int(hashlib.sha256(seed.encode("utf-8")).hexdigest(), 16) % len(variants)
    return variants[idx]


def _intent_guidance(intent):
    intent_map = {
        "recipe": "Write a real recipe with clear ingredients, steps, timings, serving yield, and practical tips. Keep claims concrete.",
        "news": "Focus on what changed, why it matters now, and cite source-backed facts with caution language.",
        "buyer": "Focus on availability, authenticity checks, pricing caveats, and decision criteria.",
        "explainer": "Focus on definitions, context, misconceptions, and concise answers.",
        "refresh": "Treat this as an update to an existing page. Emphasize what changed and refresh stale sections.",
        "trend": "Focus on evidence of momentum, drivers of growth, and likely short-term direction.",
    }
    return intent_map.get((intent or "").strip().lower(), intent_map["explainer"])


def build_article_prompt(topic_title, source_texts, matched_keyword="", intent="general"):
    """
    Build the master SEO prompt for Gemini article generation.
    """
    is_recipe = (intent or "").strip().lower() == "recipe"
    sources_block = ""
    for i, src in enumerate(source_texts[:5], 1):
        sources_block += f"""
--- SOURCE {i} ({src.get('source_domain', 'Unknown')}) ---
{src.get('text', '')[:2000]}
"""

    primary_keyword = (matched_keyword or topic_title).strip()
    keyword_pool = []
    for candidate in [primary_keyword, topic_title]:
        if candidate and candidate not in keyword_pool:
            keyword_pool.append(candidate)
    for src in source_texts[:5]:
        for candidate in [src.get("title", ""), src.get("source_domain", "")]:
            candidate = (candidate or "").strip()
            if candidate and candidate not in keyword_pool:
                keyword_pool.append(candidate)
    secondary_keywords = ", ".join(keyword_pool[1:4]) or "Use close topical variations only when naturally supported."
    supporting_keywords = ", ".join(keyword_pool[4:8]) or "Use supporting entities, ingredients, brands, locations, and use-cases only when source-backed."

    links_suggestion = "\n".join(
        f"  - [{info['anchor']}]({info['url']})"
        for info in _load_internal_links().values()
    )

    variant = _pick_layout_variant(topic_title, matched_keyword)
    outline = "\n".join(f"  - {item}" for item in variant["outline"])
    if is_recipe:
        variant = {
            "name": "Recipe Format",
            "outline": [
                "Short hook and quick summary",
                "Recipe snapshot (yield, times, key notes)",
                "Ingredients list",
                "Step-by-step instructions",
                "Tips, substitutions, and variations",
                "Storage and make-ahead guidance",
                "Serving suggestions and brief FAQ if useful",
            ],
        }
        outline = "\n".join(f"  - {item}" for item in variant["outline"])

    prompt = f"""You are an expert food journalist and recipe writer for el-mordjene.info.
Write one complete, publish-ready article with high factual reliability and high user value.

TASK:
- TRENDING TOPIC: {topic_title}
- PRIMARY KEYWORD: {matched_keyword or topic_title}
- SECONDARY KEYWORDS: {secondary_keywords}
- SUPPORTING KEYWORDS / ENTITIES: {supporting_keywords}

SOURCE MATERIAL (use only these facts):
{sources_block}

NON-NEGOTIABLE RULES:
1. Do not fabricate facts, prices, legal claims, ingredient data, or nutrition details.
2. If sources conflict, mention that explicitly and present both sides.
3. Use one language for the entire article: English OR French, never mixed.
4. Keep primary keyword density under 0.8 percent in paragraph text.
5. No emojis in body copy.
6. Do not output WordPress block comments like <!-- wp:... -->.
7. Write original synthesis for readers, not stitched or lightly rewritten source passages.
8. If source evidence is thin or uncertain, say so plainly instead of padding the article.
9. Do not create sections, FAQs, or claims whose main purpose is ranking rather than helping the reader.
10. Do not talk about search popularity, Google Trends, "people are searching for", or "this topic is trending" unless the article is specifically about search/marketing data.

LAYOUT VARIANT TO USE:
- Variant: {variant['name']}
- Outline:
{outline}

INTENT GUIDANCE:
- Intent: {intent}
- {_intent_guidance(intent)}

STYLE REQUIREMENTS:
- Output clean HTML only for the article body.
- Do not use <h1> anywhere in the article body. WordPress title is already the only H1.
- Start visible section headings at <h2> and use <h3> only for subsections.
- Use natural heading hierarchy with varied section names.
- Keep paragraphs short and readable.
- Include one key-takeaways box and one practical tip box.
- Include one CTA section near the end with wording that matches the topic.
- Begin with a strong 2-3 sentence hook that matches search intent and gives readers a reason to continue.
- In the first 120 words, give a direct answer or clear summary before expanding into details.
- The article body must not repeat the exact title as a visible heading.
- Cover the topic comprehensively: definition/context, what matters now, practical details, caveats, alternatives or variations, and a concise conclusion.
- Prefer concrete specifics over generic adjectives. Every major section should add new information.

RECIPE ARTICLE RULES (ONLY IF THIS IS A RECIPE):
- Use a full recipe structure with clear sections for Ingredients and Instructions.
- Present ingredients as a <ul><li> list, and instructions as an <ol><li> list.
- Include a concise "Recipe Snapshot" section with yield and prep/cook/total time.
- Provide substitutions, variations, and storage guidance when supported by sources.
- Do not invent nutrition facts or timings if they are not supported by sources.
- Category MUST be "Recipes" (or "Recettes" if the output language is French).

SEARCH AND HELPFULNESS REQUIREMENTS:
- Treat PRIMARY KEYWORD as a guidance signal, not something to force unnaturally.
- Use the focus keyword naturally when it genuinely helps clarity in the TITLE, META_DESCRIPTION, SLUG, and early body copy.
- Use SECONDARY KEYWORDS and SUPPORTING KEYWORDS naturally across subheadings and body text only when they improve topical completeness.
- Keep the title compelling and clear, not vague, clickbait, or artificially optimized.
- Make the meta description specific and benefit-driven while staying within 140-160 characters.
- Structure the article for quick comprehension first, then supporting detail.
- Use clear entities, product names, and context so readers can immediately understand what the page is about.
- Expand into adjacent entities, ingredients, cuisines, product types, and cultural context only when the sources support it.
- Do not force El Mordjene, Dubai chocolate, or angel hair chocolate references unless they are central to this specific topic.
- Avoid keyword stuffing, filler intros, generic conclusions, and near-duplicate template phrasing.
- Build topical depth, not just keyword repetition. The article should feel complete even if a reader never saw the source articles.

FAQ AND SCHEMA RULES:
- Add FAQ only if it materially helps readers and the answers are supported by the source material.
- If FAQ is included, include valid FAQPage JSON-LD wrapped in:
  <script type="application/ld+json"> ... </script>
- Do NOT include Recipe JSON-LD in the HTML body.
- Recipe schema is generated by the system separately for real recipe posts.

INTERNAL LINKING RULES:
- Use exactly 2-3 internal links from the approved list below.
- Never invent URLs.

Allowed internal links:
{links_suggestion}

EXTERNAL LINKING RULES:
- Include exactly ONE high-quality, high-authority external link (e.g., to a reputable news source, official government site, or recognized culinary authority).
- The external link must be highly relevant to the topic.
- Format the external link to open in a new tab: <a href="..." target="_blank" rel="noopener noreferrer">...</a>


RECIPE DATA REQUIREMENTS:
If this is a real recipe article, output a strict JSON object with all recipe fields filled as completely as possible from the article and source material. If not, output {{}}.
For recipe articles, do not leave ingredients or instructions empty.
Required JSON fields:
- recipe_name (string)
- recipe_description (string)
- recipe_yield (string)
- prep_time_minutes (number)
- cook_time_minutes (number)
- total_time_minutes (number or empty string)
- ingredients (string, one ingredient per line)
- instructions (string, one step per line)
- recipe_image (string, keep empty)
- nutrition_calories (string)
- video_url (string, empty if none)
- author_name (string, optional)
- recipe_keywords (string)
- recipecuisine (string)
- recipecategory (string)
- video_upload_date (YYYY-MM-DD or empty)

OUTPUT FORMAT (STRICT):
TITLE: [under 60 chars]
META_DESCRIPTION: [140-160 chars]
SLUG: [lowercase-hyphenated]
TAGS: [tag1, tag2, tag3]
CATEGORY: [Recipes OR Food News OR Trends OR Sweets]
LANGUAGE: [en or fr]

---CONTENT_START---
[Raw HTML article body only]
---CONTENT_END---

---RECIPE_DATA_START---
[Raw JSON object only, no markdown fences]
---RECIPE_DATA_END---
"""

    return prompt


def build_image_prompt(topic_title, article_content_snippet=""):
    """Build a prompt for generating a food photography featured image."""
    prompt = f"""Generate a stunning, appetizing food photography image suitable for a professional food blog or culinary magazine like Bon Appetit or Tasty.

Context: This image is for a food article about: {topic_title}

CRITICAL INSTRUCTIONS:
- ABSOLUTELY NO TEXT, NO LETTERS, NO WORDS, NO NUMBERS, AND NO WATERMARKS anywhere in the image.
- DO NOT attempt to write the topic title or any keywords on the image.
- DO NOT include graphic design overlays, borders, or lower-thirds.

Style & Composition Guidelines:
- Professional food photography, overhead or 45-degree angle
- Warm, natural lighting with soft shadows (like golden hour or window light)
- Rich, vibrant colors that make food look irresistible
- Clean, styled background (marble, wood, linen, or rustic surfaces)
- Include garnishes, scattered ingredients, or utensils for visual interest
- 16:9 aspect ratio, landscape orientation
- The image should make the viewer hungry and inspired to cook

Exclusions:
- No recognizable brand logos or packaging
- No human faces (hands holding food are OK)
- No cluttered or messy backgrounds"""

    return prompt




