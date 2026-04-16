"""
NewsAPI Monitor - Fetches food, sweets, and confectionery headlines from NewsAPI.
"""
import logging
import hashlib
from datetime import datetime, timedelta

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import config

logger = logging.getLogger(__name__)


def _hash_story(title, url):
    """Create a unique hash for a story."""
    raw = f"{title.strip().lower()}|{url.strip().lower()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def fetch_news_headlines():
    """
    Fetch food-related headlines from NewsAPI.
    Returns a list of story dicts.
    """
    stories = []

    if not config.NEWS_API_KEY:
        logger.debug("NEWS_API_KEY not configured. Skipping NewsAPI.")
        return stories

    try:
        from newsapi import NewsApiClient
        newsapi = NewsApiClient(api_key=config.NEWS_API_KEY)
    except ImportError:
        logger.warning("newsapi-python not installed. Skipping NewsAPI.")
        return stories
    except Exception as e:
        logger.error(f"Failed to initialize NewsAPI client: {e}")
        return stories

    for query in getattr(config, "NEWSAPI_SEARCH_QUERIES", []):
        try:
            logger.info(f"NewsAPI: Searching for '{query}'")
            from_date = (datetime.utcnow() - timedelta(hours=48)).strftime("%Y-%m-%d")

            results = newsapi.get_everything(
                q=query,
                sort_by="publishedAt",
                language="en",
                from_param=from_date,
                page_size=10,
            )

            if results.get("status") == "ok":
                for article in results.get("articles", []):
                    title = article.get("title", "")
                    if not title or title == "[Removed]":
                        continue

                    combined = f"{title} {article.get('description', '')}".lower()
                    if any(kw.lower() in combined for kw in config.EXCLUDE_KEYWORDS):
                        continue

                    stories.append({
                        "title": title.strip(),
                        "summary": (article.get("description") or "").strip()[:500],
                        "url": article.get("url", ""),
                        "source": f"NewsAPI/{article.get('source', {}).get('name', 'Unknown')}",
                        "source_type": "newsapi",
                        "matched_keyword": query.lower(),
                        "published_at": _parse_date(article.get("publishedAt")),
                        "story_hash": _hash_story(title, article.get("url", "")),
                        "image_url": article.get("urlToImage", ""),
                    })

        except Exception as e:
            logger.error(f"NewsAPI error for '{query}': {e}")
            continue

    seen_hashes = set()
    unique = []
    for story in stories:
        if story["story_hash"] not in seen_hashes:
            seen_hashes.add(story["story_hash"])
            unique.append(story)

    logger.info(f"NewsAPI Monitor: Found {len(unique)} relevant stories")
    return unique


def _parse_date(date_str):
    """Parse ISO date string from NewsAPI."""
    if not date_str:
        return datetime.utcnow()
    try:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00")).replace(tzinfo=None)
    except Exception:
        return datetime.utcnow()
