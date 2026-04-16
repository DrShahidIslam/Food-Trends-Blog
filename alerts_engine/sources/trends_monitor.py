"""
Google Trends Monitor - Tracks rising search queries related to food, recipes, and desserts.
"""
import logging
import time
from datetime import datetime

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import config

logger = logging.getLogger(__name__)


def _build_keyword_batches(keywords, batch_size=5):
    """Split keywords into batches of 5 (pytrends limit per request)."""
    for i in range(0, len(keywords), batch_size):
        yield keywords[i:i + batch_size]


def fetch_trending_queries():
    """
    Check Google Trends for rising interest in food-related keywords.
    Returns a list of trend dicts with keyword, interest score, and rising status.
    """
    trends = []

    try:
        from pytrends.request import TrendReq
        pytrends = TrendReq(hl='en-US', tz=0, timeout=(10, 30))
    except ImportError:
        logger.warning("pytrends not installed. Skipping Google Trends.")
        return trends
    except Exception as e:
        logger.error(f"Failed to initialize pytrends: {e}")
        return trends

    core_keywords = list(getattr(config, "TRENDS_CORE_KEYWORDS", []))
    batch_size = int(getattr(config, "TRENDS_KEYWORDS_PER_BATCH", 5))

    for batch in _build_keyword_batches(core_keywords, batch_size=batch_size):
        try:
            logger.info(f"Checking Google Trends for: {batch}")
            pytrends.build_payload(batch, cat=0, timeframe='now 7-d', geo=config.TRENDS_GEO)

            interest_df = pytrends.interest_over_time()
            if interest_df is not None and not interest_df.empty:
                for keyword in batch:
                    if keyword in interest_df.columns:
                        values = interest_df[keyword].tolist()
                        if len(values) >= 2:
                            current = values[-1]
                            avg_overall = sum(values) / len(values)
                            is_rising = current > avg_overall * 1.5

                            velocity = 0.0
                            if len(values) >= 4:
                                recent_avg = sum(values[-3:]) / 3
                                older_avg = sum(values[:3]) / 3
                                velocity = (recent_avg - older_avg) / max(older_avg, 1)

                            trends.append({
                                "keyword": keyword,
                                "current_interest": int(current),
                                "avg_interest": round(avg_overall, 1),
                                "is_rising": is_rising,
                                "spike_ratio": round(current / max(avg_overall, 1), 2),
                                "velocity": round(velocity, 2),
                                "source": "google_trends",
                                "source_type": "trends",
                                "recorded_at": datetime.utcnow(),
                            })

                            if is_rising:
                                logger.info(
                                    f"  Rising: '{keyword}' - {current} vs avg {avg_overall:.0f} "
                                    f"({current / max(avg_overall, 1):.1f}x, velocity: {velocity:.2f})"
                                )

            time.sleep(5)

        except Exception as e:
            logger.warning(f"Google Trends error for batch {batch}: {e}")
            time.sleep(10)
            continue

    for core_topic in getattr(config, "TRENDS_RELATED_TOPICS", []):
        try:
            pytrends.build_payload([core_topic], cat=0, timeframe='now 7-d', geo=config.TRENDS_GEO)
            related = pytrends.related_queries()

            if related and core_topic in related:
                rising_df = related[core_topic].get("rising")
                if rising_df is not None and not rising_df.empty:
                    for _, row in rising_df.head(10).iterrows():
                        query = row.get("query", "")
                        value = row.get("value", 0)
                        query_lower = query.lower()

                        if any(ex_kw.lower() in query_lower for ex_kw in getattr(config, "EXCLUDE_KEYWORDS", [])):
                            continue

                        trends.append({
                            "keyword": query,
                            "current_interest": int(value) if isinstance(value, (int, float)) else 0,
                            "avg_interest": 0,
                            "is_rising": True,
                            "spike_ratio": 0,
                            "velocity": 0,
                            "source": "google_trends_related",
                            "source_type": "trends",
                            "recorded_at": datetime.utcnow(),
                        })
                        logger.info(f"  Related rising query: '{query}' (value: {value})")

            time.sleep(5)

        except Exception as e:
            logger.warning(f"Related queries error for '{core_topic}': {e}")

    if getattr(config, "ENABLE_REALTIME_TRENDS", True):
        try:
            realtime = get_realtime_trending()
            trends.extend(realtime)
        except Exception as e:
            logger.warning(f"Real-time trends merge error: {e}")

    deduped = []
    seen = set()
    for item in trends:
        key = (item.get("keyword", "").strip().lower(), item.get("source", "").strip().lower())
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)

    logger.info(f"Trends Monitor: Found {len(deduped)} data points, {sum(1 for t in deduped if t['is_rising'])} rising")
    return deduped


def get_realtime_trending():
    """Fetch real-time trending searches and filter for food-related topics."""
    realtime_trends = []

    try:
        from pytrends.request import TrendReq
        pytrends = TrendReq(hl='en-US', tz=0)
        trending = pytrends.trending_searches(pn='united_states')

        if trending is not None and not trending.empty:
            for _, row in trending.iterrows():
                query = str(row[0]).lower()
                for kw in config.ALL_KEYWORDS:
                    if kw.lower() in query or any(word in query for word in kw.lower().split()):
                        realtime_trends.append({
                            "keyword": str(row[0]),
                            "source": "google_trending",
                            "source_type": "realtime_trends",
                            "is_rising": True,
                            "matched_keyword": kw,
                            "recorded_at": datetime.utcnow(),
                        })
                        logger.info(f"  Real-time trending: '{row[0]}' (matched: {kw})")
                        break

    except ImportError:
        logger.warning("pytrends not installed. Skipping real-time trends.")
    except Exception as e:
        logger.warning(f"Real-time trending error: {e}")

    return realtime_trends
