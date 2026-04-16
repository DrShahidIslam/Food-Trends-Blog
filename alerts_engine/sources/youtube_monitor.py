"""
YouTube Monitor — Searches for trending recipe/dessert videos using the YouTube Data API.
Only active when YOUTUBE_API_KEY is configured in .env.
"""
import hashlib
import logging
from datetime import datetime

import requests

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import config

logger = logging.getLogger(__name__)


def _hash_story(title, url):
    """Create a unique hash for a video."""
    raw = f"{title.strip().lower()}|{url.strip().lower()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def fetch_youtube_videos():
    """
    Search YouTube for trending food/recipe videos matching configured queries.
    Uses the YouTube Data API v3 (free tier: 10,000 units/day; search = 100 units).
    Returns a list of story dicts compatible with the detection pipeline.
    """
    if not config.YOUTUBE_API_KEY:
        logger.debug("YouTube API key not configured. Skipping YouTube source.")
        return []

    stories = []
    api_base = "https://www.googleapis.com/youtube/v3/search"

    # Limit queries to conserve API quota (each search = 100 units)
    queries = getattr(config, "YOUTUBE_SEARCH_QUERIES", [])[:6]

    for query in queries:
        try:
            params = {
                "part": "snippet",
                "q": query,
                "type": "video",
                "order": "date",
                "maxResults": 5,
                "publishedAfter": _get_recent_cutoff(),
                "key": config.YOUTUBE_API_KEY,
            }

            response = requests.get(api_base, params=params, timeout=15)
            if response.status_code != 200:
                logger.warning(f"YouTube API error for '{query}': HTTP {response.status_code}")
                if response.status_code == 403:
                    logger.error("YouTube API quota exceeded or key invalid. Stopping YouTube searches.")
                    break
                continue

            data = response.json()
            for item in data.get("items", []):
                snippet = item.get("snippet", {})
                video_id = item.get("id", {}).get("videoId", "")
                title = snippet.get("title", "")
                description = snippet.get("description", "")
                channel = snippet.get("channelTitle", "")
                published = snippet.get("publishedAt", "")

                if not title or not video_id:
                    continue

                url = f"https://www.youtube.com/watch?v={video_id}"

                # Check against exclusion keywords
                combined = f"{title} {description}".lower()
                excluded = any(kw.lower() in combined for kw in config.EXCLUDE_KEYWORDS)
                if excluded:
                    continue

                # Determine matched keyword
                matched_keyword = query
                for kw in config.ALL_KEYWORDS:
                    if kw.lower() in combined:
                        matched_keyword = kw
                        break

                story = {
                    "title": title.strip(),
                    "summary": description.strip()[:500],
                    "url": url,
                    "source": f"YouTube/{channel}",
                    "source_type": "youtube",
                    "matched_keyword": matched_keyword,
                    "published_at": _parse_iso_date(published),
                    "story_hash": _hash_story(title, url),
                    "channel": channel,
                    "video_id": video_id,
                }
                stories.append(story)
                logger.debug(f"  ✓ YouTube: {title[:80]} [{channel}]")

        except Exception as e:
            logger.error(f"YouTube search error for '{query}': {e}")
            continue

    # Deduplicate
    seen = set()
    unique = []
    for s in stories:
        if s["story_hash"] not in seen:
            seen.add(s["story_hash"])
            unique.append(s)

    logger.info(f"YouTube Monitor: Found {len(unique)} relevant videos")
    return unique


def _get_recent_cutoff():
    """Get ISO date string for 48 hours ago (YouTube API publishedAfter format)."""
    from datetime import timedelta
    cutoff = datetime.utcnow() - timedelta(hours=48)
    return cutoff.strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_iso_date(date_str):
    """Parse ISO date string from YouTube API."""
    if not date_str:
        return datetime.utcnow()
    try:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00")).replace(tzinfo=None)
    except Exception:
        return datetime.utcnow()


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    videos = fetch_youtube_videos()
    for v in videos[:10]:
        print(f"[{v['source']}] {v['title']}")
        print(f"  Keyword: {v['matched_keyword']} | URL: {v['url']}")
        print()
