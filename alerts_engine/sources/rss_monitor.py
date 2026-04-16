"""
RSS Feed Monitor - Fetches and filters food, sweets, and dessert stories from curated RSS feeds.
"""
import feedparser
import hashlib
import logging
import re
import unicodedata
from datetime import datetime

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import config

logger = logging.getLogger(__name__)


def _normalize(text):
    """Lowercase, remove accents, and strip punctuation for keyword matching."""
    normalized = unicodedata.normalize("NFKD", text or "")
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    return re.sub(r'[^a-z0-9\s]', '', ascii_text.lower())


def _matches_keywords(text, keywords=None):
    """Check if text matches any food-related keywords."""
    if keywords is None:
        keywords = config.ALL_KEYWORDS
    normalized = _normalize(text)
    for kw in keywords:
        normalized_kw = _normalize(kw)
        if normalized_kw and normalized_kw in normalized:
            return True, kw
    return False, None


def _hash_story(title, url):
    """Create a unique hash for a story based on title + URL."""
    raw = f"{title.strip().lower()}|{url.strip().lower()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def fetch_rss_stories():
    """
    Fetch stories from all configured RSS feeds.
    Applies keyword matching and exclusion filtering.
    Returns a list of story dicts.
    """
    stories = []

    for feed_name, feed_url in config.RSS_FEEDS.items():
        try:
            logger.info(f"Fetching RSS: {feed_name}")
            feed = feedparser.parse(feed_url)

            if feed.bozo and not feed.entries:
                logger.warning(f"RSS feed error for {feed_name}: {feed.bozo_exception}")
                continue

            for entry in feed.entries[:30]:
                title = entry.get("title", "")
                summary = entry.get("summary", entry.get("description", ""))
                link = entry.get("link", "")
                combined_text = f"{title} {summary}"
                is_match, matched_keyword = _matches_keywords(combined_text)

                if not is_match:
                    continue

                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    try:
                        published = datetime(*entry.published_parsed[:6])
                    except Exception:
                        published = datetime.utcnow()
                else:
                    published = datetime.utcnow()

                stories.append({
                    "title": title.strip(),
                    "summary": summary.strip()[:500],
                    "url": link.strip(),
                    "source": feed_name,
                    "source_type": "rss",
                    "matched_keyword": matched_keyword,
                    "published_at": published,
                    "story_hash": _hash_story(title, link),
                })
                logger.debug(f"  Matched: {title[:80]} [{matched_keyword}]")

        except Exception as e:
            logger.error(f"Error fetching RSS feed {feed_name}: {e}")
            continue

    filtered = []
    excluded_count = 0
    for story in stories:
        text = f"{story.get('title', '')} {story.get('summary', '')}".lower()
        if any(kw.lower() in text for kw in getattr(config, "EXCLUDE_KEYWORDS", [])):
            excluded_count += 1
            continue
        filtered.append(story)

    if excluded_count > 0:
        logger.info(f"RSS Monitor: Excluded {excluded_count} irrelevant stories")

    seen_hashes = set()
    unique = []
    for story in filtered:
        if story["story_hash"] not in seen_hashes:
            seen_hashes.add(story["story_hash"])
            unique.append(story)

    logger.info(f"RSS Monitor: Found {len(unique)} relevant stories across {len(config.RSS_FEEDS)} feeds")
    return unique
