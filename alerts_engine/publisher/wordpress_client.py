"""
WordPress Client â€” Handles all WordPress REST API interactions:
creating posts, uploading media, setting categories/tags,
and injecting RankMath SEO fields.
"""
import base64
import logging
import os
import re
import json
import time
import requests
from requests.auth import HTTPBasicAuth

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import config

logger = logging.getLogger(__name__)

# Set when publish fails so Telegram can show the reason
LAST_PUBLISH_ERROR = None

API_BASE = f"{config.WP_URL}/wp-json/wp/v2"
AUTH = HTTPBasicAuth(config.WP_USERNAME, config.WP_APP_PASSWORD)
TIMEOUT = 30
RETRY_DELAY = 5
RETRY_403_DELAY = 4
RECIPE_CATEGORY_NAMES = {"recipes", "recettes"}
RECIPE_TITLE_MARKERS = [
    "recipe",
    "recette",
    "how to make",
    "ingredients",
    "instructions",
    "homemade",
    "copycat",
]
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; ElMordjeneAgent/1.0; +https://el-mordjene.info)",
    "Referer": f"{config.WP_URL}/",
    "Accept": "application/json, */*; q=0.1",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": config.WP_URL.rstrip("/"),
}

def _safe_json(response, context_name=""):
    try:
        return response.json()
    except ValueError:
        text = response.text[:200] if response.text else "<empty body>"
        logger.error(f"  {context_name} expected JSON but got HTTP {response.status_code}: {text}")
        raise ValueError(f"WP non-JSON response ({response.status_code}) on {context_name}: {text}")



def _is_recipe_article(article):
    if not isinstance(article, dict):
        return False
    if str(article.get("intent", "")).strip().lower() == "recipe":
        return True
    category = str(article.get("category", "")).strip().lower()
    if category in RECIPE_CATEGORY_NAMES:
        return True
    title = str(article.get("title", "")).strip().lower()
    slug = str(article.get("slug", "")).strip().lower()
    tags = " ".join(article.get("tags", [])).strip().lower()
    if any(marker in title for marker in RECIPE_TITLE_MARKERS):
        return True
    if any(marker in slug for marker in RECIPE_TITLE_MARKERS):
        return True
    if any(marker in tags for marker in RECIPE_TITLE_MARKERS):
        return True
    acf_fields = article.get("acf_fields", {}) or {}
    if acf_fields.get("ingredients") or acf_fields.get("instructions") or acf_fields.get("recipe_name"):
        return True
    return False


def _force_recipe_category(article):
    if not _is_recipe_article(article):
        return
    language = str(article.get("language", "en")).strip().lower()
    if language == "fr":
        article["category"] = config.WP_RECIPE_CATEGORY_FR
        article["category_slug"] = config.WP_RECIPE_CATEGORY_SLUG_FR
    else:
        article["category"] = config.WP_RECIPE_CATEGORY_EN
        article["category_slug"] = config.WP_RECIPE_CATEGORY_SLUG_EN


def _prepare_acf_payload(article, media_id=None):
    acf_data = dict(article.get("acf_fields", {}) or {})
    if not acf_data:
        return {}

    if media_id:
        acf_data["recipe_image"] = media_id

    normalized = {}
    for key, value in acf_data.items():
        if value in (None, ""):
            continue
        if isinstance(value, list):
            normalized[key] = "\n".join(str(item).strip() for item in value if str(item).strip())
        else:
            normalized[key] = value

    logger.info(f"  Prepared ACF payload keys: {sorted(normalized.keys())}")
    return normalized


def create_post(article, featured_image_path=None, status=None):
    """
    Create a WordPress post from an article dict.
    If WP_PUBLISH_WEBHOOK_URL and WP_PUBLISH_SECRET are set, publishes via webhook.
    Otherwise uses REST API.
    """
    _force_recipe_category(article)
    if status is None:
        status = config.WP_DEFAULT_STATUS

    global LAST_PUBLISH_ERROR
    LAST_PUBLISH_ERROR = None

    if getattr(config, "WP_PUBLISH_WEBHOOK_URL", None) and getattr(config, "WP_PUBLISH_SECRET", None):
        out = _publish_via_webhook(article, featured_image_path, status)
        if out is None and LAST_PUBLISH_ERROR:
            logger.error(f"  Webhook: {LAST_PUBLISH_ERROR}")
        return out

    logger.info(f"Publishing to WordPress: '{article.get('title', 'Untitled')}'")

    # Step 1: Upload featured image
    media_id = None
    if featured_image_path and os.path.exists(featured_image_path):
        media_id = upload_media(featured_image_path, article.get("title", ""))

    # Step 2: Get or create category
    category_slug = article.get("category_slug", "")
    category_name = article.get("category", config.WP_DEFAULT_CATEGORY)
    category_id = get_or_create_category(category_name, slug=category_slug)

    # Step 3: Get or create tags
    tag_ids = []
    for tag_name in article.get("tags", []):
        tag_id = get_or_create_tag(tag_name)
        if tag_id:
            tag_ids.append(tag_id)

    # Step 4: Create the post
    post_data = {
        "title": article.get("title", "Untitled"),
        "content": article.get("full_content", article.get("content", "")),
        "excerpt": article.get("meta_description", ""),
        "slug": article.get("slug", ""),
        "status": status,
        "categories": [category_id] if category_id else [],
        "tags": tag_ids,
        "comment_status": "open",
        "lang": article.get("language", "en"),
    }

    if media_id:
        post_data["featured_media"] = media_id

    # Add ACF Fields if we have them
    acf_data = _prepare_acf_payload(article, media_id=media_id)
    if acf_data:
        post_data["acf"] = acf_data

    try:
        for attempt in range(3):
            response = requests.post(
                f"{API_BASE}/posts",
                json=post_data,
                auth=AUTH,
                headers=HEADERS,
                timeout=TIMEOUT,
            )
            if response.status_code in (200, 201):
                result = _safe_json(response, "Post Creation")
                post_id = result.get("id")
                post_url = result.get("link", "")

                logger.info(f"  Post created (ID: {post_id}, Status: {status})")
                logger.info(f"  URL: {post_url}")

                _set_rankmath_meta(post_id, article)

                if acf_data:
                    logger.info(f"  REST ACF payload submitted with {len(acf_data)} fields")
                return {
                    "post_id": post_id,
                    "post_url": post_url,
                    "status": status,
                }
            if response.status_code in (502, 503) and attempt < 2:
                logger.warning(f"  WordPress {response.status_code}, retrying in {RETRY_DELAY}s...")
                time.sleep(RETRY_DELAY)
                continue
            if response.status_code == 403 and attempt < 2:
                logger.warning(f"  403 Forbidden, retrying in {RETRY_403_DELAY}s...")
                time.sleep(RETRY_403_DELAY)
                continue
            break

        logger.error(f"  Post creation failed: HTTP {response.status_code}")
        logger.error(f"     Response: {response.text[:500]}")
        LAST_PUBLISH_ERROR = f"REST HTTP {response.status_code}"
        return None

    except Exception as e:
        logger.error(f"  Post creation error: {e}")
        LAST_PUBLISH_ERROR = str(e)[:120]
        return None


def _publish_via_webhook(article, featured_image_path=None, status=None):
    """Publish via webhook on the user's server."""
    global LAST_PUBLISH_ERROR
    url = config.WP_PUBLISH_WEBHOOK_URL
    secret = config.WP_PUBLISH_SECRET
    if not url or not secret:
        return None

    payload = {
        "title": article.get("title", "Untitled"),
        "content": article.get("full_content", article.get("content", "")),
        "excerpt": article.get("meta_description", ""),
        "slug": article.get("slug", ""),
        "status": status or config.WP_DEFAULT_STATUS,
        "tags": article.get("tags", []),
        "category": article.get("category", config.WP_DEFAULT_CATEGORY),
        "rank_math_title": article.get("title", ""),
        "rank_math_description": article.get("meta_description", ""),
        "rank_math_focus_keyword": article.get("matched_keyword", "") or (article.get("tags") or [""])[0],
        "language": article.get("language", "en"),
    }

    acf_data = _prepare_acf_payload(article)
    if acf_data:
        payload["acf"] = acf_data
        payload["acf_fields"] = acf_data
        payload["recipe_fields"] = acf_data
        payload["is_recipe"] = True

    if featured_image_path and os.path.exists(featured_image_path):
        with open(featured_image_path, "rb") as f:
            payload["featured_image_base64"] = base64.b64encode(f.read()).decode("ascii")
        payload["featured_image_filename"] = os.path.basename(featured_image_path)
        payload["featured_image_alt"] = article.get("title", "")

    for attempt in range(3):
        headers = HEADERS.copy()
        headers.update({
            "Content-Type": "application/json",
            "X-ElMordjene-Agent-Token": secret,
        })

        try:
            r = requests.post(url, json=payload, headers=headers, timeout=60)
            if r.status_code == 200:
                data = r.json()
                if data.get("success"):
                    logger.info(f"  Post created via webhook (ID: {data.get('post_id')})")
                    if acf_data:
                        logger.info(f"  Webhook ACF payload submitted with {len(acf_data)} fields")
                    return {
                        "post_id": data.get("post_id"),
                        "post_url": data.get("post_url", ""),
                        "status": data.get("status", status),
                    }
                logger.error(f"  Webhook returned success=false: {data.get('message', '')}")
                LAST_PUBLISH_ERROR = data.get("message", "success=false")
                return None
            if r.status_code in (502, 503, 403) and attempt < 2:
                logger.warning(f"  Webhook {r.status_code}, retrying in {RETRY_DELAY}s...")
                time.sleep(RETRY_DELAY)
                continue
            err = f"HTTP {r.status_code}"
            if r.text and len(r.text) < 200:
                err += f" â€” {r.text.strip()}"
            logger.error(f"  Webhook failed: {err}")
            LAST_PUBLISH_ERROR = err
            return None
        except Exception as e:
            logger.warning(f"  Webhook request error (attempt {attempt + 1}/3): {e}")
            LAST_PUBLISH_ERROR = str(e)[:150]
            if attempt < 2:
                time.sleep(RETRY_DELAY)
    return None


def upload_media(file_path, title=""):
    """Upload an image file to WordPress media library."""
    filename = os.path.basename(file_path)
    mime_type = _get_mime_type(filename)

    try:
        with open(file_path, "rb") as f:
            file_data = f.read()
        headers = HEADERS.copy()
        headers.update({
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Type": mime_type,
        })

        for attempt in range(3):
            response = requests.post(
                f"{API_BASE}/media",
                data=file_data,
                headers=headers,
                auth=AUTH,
                timeout=60,
            )
            if response.status_code in (200, 201):
                media_id = _safe_json(response, "Media Upload").get("id")
                logger.info(f"  Image uploaded (Media ID: {media_id})")

                if title:
                    requests.post(
                        f"{API_BASE}/media/{media_id}",
                        json={"alt_text": title[:125]},
                        auth=AUTH,
                        headers=HEADERS,
                        timeout=15,
                    )
                return media_id
            if response.status_code in (502, 503) and attempt < 2:
                time.sleep(RETRY_DELAY)
                continue
            if response.status_code == 403 and attempt < 2:
                time.sleep(RETRY_403_DELAY)
                continue
            break

        logger.error(f"  Media upload failed: HTTP {response.status_code}")
        return None

    except Exception as e:
        logger.error(f"  Media upload error: {e}")
        return None


def get_or_create_category(name, slug=""):
    """Get category ID by name (or slug), creating it only for non-recipe categories."""
    try:
        # Try slug-based lookup first (most reliable for recipe categories)
        if slug:
            response = requests.get(
                f"{API_BASE}/categories",
                params={"slug": slug},
                auth=AUTH, headers=HEADERS, timeout=TIMEOUT
            )
            if response.status_code == 200:
                cats = _safe_json(response, "Get Category by Slug")
                if cats:
                    cat_id = cats[0]["id"]
                    logger.info(f"  Found category by slug '{slug}' (ID: {cat_id}, Name: '{cats[0]['name']}')")
                    return cat_id

        # Fallback: search by name
        response = requests.get(
            f"{API_BASE}/categories",
            params={"search": name, "per_page": 10},
            auth=AUTH, headers=HEADERS, timeout=TIMEOUT
        )
        if response.status_code == 200:
            for cat in _safe_json(response, "Get Category"):
                if cat["name"].lower() == name.lower():
                    logger.info(f"  Found category by name '{name}' (ID: {cat['id']})")
                    return cat["id"]
                # Also check slug match as secondary fallback
                if slug and cat.get("slug", "").lower() == slug.lower():
                    logger.info(f"  Found category by slug match '{slug}' (ID: {cat['id']}, Name: '{cat['name']}')")
                    return cat["id"]

        # For recipe categories, do NOT auto-create — it causes ACF schema issues
        is_recipe_cat = name.lower() in RECIPE_CATEGORY_NAMES
        if is_recipe_cat:
            logger.error(f"  Recipe category '{name}' (slug: '{slug}') NOT FOUND in WordPress — skipping creation to avoid duplicates")
            return None

        # For non-recipe categories, create as before
        response = requests.post(
            f"{API_BASE}/categories",
            json={"name": name},
            auth=AUTH, headers=HEADERS, timeout=TIMEOUT
        )
        if response.status_code in (200, 201):
            cat_id = _safe_json(response, "Create Category").get("id")
            logger.info(f"  Created category '{name}' (ID: {cat_id})")
            return cat_id

    except Exception as e:
        logger.error(f"  Category error for '{name}': {e}")
    return None


def get_or_create_tag(name):
    """Get tag ID by name, creating it if it doesn't exist."""
    try:
        response = requests.get(
            f"{API_BASE}/tags",
            params={"search": name, "per_page": 5},
            auth=AUTH, headers=HEADERS, timeout=TIMEOUT
        )
        if response.status_code == 200:
            for tag in _safe_json(response, "Get Tag"):
                if tag["name"].lower() == name.lower():
                    return tag["id"]

        response = requests.post(
            f"{API_BASE}/tags",
            json={"name": name},
            auth=AUTH, headers=HEADERS, timeout=TIMEOUT
        )
        if response.status_code in (200, 201):
            return _safe_json(response, "Create Tag").get("id")

    except Exception as e:
        logger.error(f"  Tag error for '{name}': {e}")
    return None


def _set_rankmath_meta(post_id, article):
    """Set RankMath SEO metadata on a post."""
    focus_kw = article.get("matched_keyword", "")
    if not focus_kw and article.get("tags"):
        focus_kw = article["tags"][0]

    rankmath_meta = {
        "meta": {
            "rank_math_title": article.get("title", ""),
            "rank_math_description": article.get("meta_description", ""),
            "rank_math_focus_keyword": focus_kw,
            "rank_math_robots": ["index", "follow"],
        }
    }

    try:
        response = requests.request(
            "PATCH",
            f"{API_BASE}/posts/{post_id}",
            json=rankmath_meta,
            auth=AUTH, headers=HEADERS, timeout=TIMEOUT,
        )
        if response.status_code == 200:
            logger.info(f"  RankMath SEO metadata set (focus: '{focus_kw}')")
        else:
            logger.warning(f"  RankMath meta update returned HTTP {response.status_code}")
    except Exception as e:
        logger.warning(f"  RankMath meta update failed: {e}")


def update_post_status(post_id, status="publish"):
    """Update a post's status (e.g., from draft to publish)."""
    if getattr(config, "WP_PUBLISH_WEBHOOK_URL", None) and getattr(config, "WP_PUBLISH_SECRET", None):
        return _update_status_via_webhook(post_id, status)
    try:
        response = requests.post(
            f"{API_BASE}/posts/{post_id}",
            json={"status": status},
            auth=AUTH, headers=HEADERS, timeout=TIMEOUT,
        )
        if response.status_code == 200:
            try:
                data = response.json()
                return {
                    "link": data.get("link"),
                    "title": data.get("title", {}).get("rendered", ""),
                    "slug": data.get("slug", "")
                }
            except (ValueError, KeyError):
                return None
        logger.error(f"Failed to update post status: HTTP {response.status_code}")
        return None
    except Exception as e:
        logger.error(f"Error updating post status: {e}")
        return None


def _update_status_via_webhook(post_id, status="publish"):
    """Update post status via webhook."""
    url = config.WP_PUBLISH_WEBHOOK_URL
    secret = config.WP_PUBLISH_SECRET
    if not url or not secret:
        return None

    try:
        headers = HEADERS.copy()
        headers.update({
            "Content-Type": "application/json",
            "X-ElMordjene-Agent-Token": secret,
        })

        r = requests.post(
            url,
            json={"action": "publish_draft", "post_id": int(post_id), "status": status},
            headers=headers, timeout=30,
        )
        if r.status_code == 200:
            try:
                data = r.json()
            except ValueError:
                return None
            if data.get("success"):
                return {
                    "link": data.get("post_url"),
                    "title": data.get("title", ""), # Assuming webhook returns title 
                    "slug": data.get("slug", "")   # and slug in success payload
                }
        return None
    except Exception as e:
        logger.warning(f"Webhook status update failed: {e}")
        return None


def get_recent_post_titles(limit=50):
    """Fetch recent post titles from WordPress to check for duplicate content."""
    titles = []
    try:
        response = requests.get(
            f"{API_BASE}/posts",
            params={"per_page": min(limit, 100), "status": "publish,draft,pending"},
            auth=AUTH, headers=HEADERS, timeout=TIMEOUT,
        )
        if response.status_code == 200:
            for post in response.json():
                title = post.get("title", {}).get("rendered", "")
                if title:
                    titles.append(title)
    except Exception as e:
        logger.warning(f"Could not fetch recent posts: {e}")
    return titles


def _get_mime_type(filename):
    """Determine MIME type from filename."""
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    mime_map = {
        "jpg": "image/jpeg", "jpeg": "image/jpeg",
        "png": "image/png", "gif": "image/gif", "webp": "image/webp",
    }
    return mime_map.get(ext, "image/jpeg")


def test_wordpress_connection():
    """Test the WordPress REST API connection."""
    try:
        response = requests.get(
            f"{API_BASE}/posts",
            params={"per_page": 1},
            auth=AUTH, headers=HEADERS, timeout=TIMEOUT
        )
        if response.status_code == 200:
            posts = _safe_json(response, "Test Connection")
            if posts:
                logger.info(f"WordPress: Connected. Latest: '{posts[0]['title']['rendered'][:50]}'")
            else:
                logger.info("WordPress: Connected. No posts found.")
            return True
        else:
            logger.error(f"WordPress: HTTP {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"WordPress connection failed: {e}")
        return False


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    if test_wordpress_connection():
        print("WordPress connection successful!")
    else:
        print("WordPress connection failed!")










