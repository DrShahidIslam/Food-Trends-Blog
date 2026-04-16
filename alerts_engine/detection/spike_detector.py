"""
Spike Detector Ã¢â‚¬â€ Aggregates stories from all sources, deduplicates,
calculates spike scores, and returns trending topics worth covering.

INTELLIGENCE FEATURES (beyond FIFA app):
- Seasonal keyword boosting (Ramadan desserts in March, Christmas chocolate in Dec)
- Trend velocity scoring (how fast a trend is growing, not just if it's rising)
- Duplicate content detection (Jaccard similarity against published articles)
- Multi-factor scoring with food-specific high-value signals
"""
import logging
import hashlib
from collections import defaultdict
from datetime import datetime

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import config
from database.db import (
    get_connection, is_story_seen, add_story, record_keyword_mention,
    get_keyword_baseline, is_topic_already_covered, get_recent_published_topics
)

logger = logging.getLogger(__name__)


def _cluster_stories(stories):
    """
    Group related stories by topic. Stories about the same recipe/trend
    from different sources get clustered together.
    """
    clusters = defaultdict(list)

    for story in stories:
        title_words = set(story["title"].lower().split())
        stop_words = {"the", "a", "an", "is", "are", "was", "were", "in", "on", "at",
                      "to", "for", "of", "with", "and", "or", "but", "not", "this",
                      "that", "it", "as", "by", "from", "has", "have", "had", "will",
                      "be", "been", "can", "could", "would", "should", "do", "does",
                      "how", "what", "why", "when", "which", "your", "you", "new"}
        key_words = title_words - stop_words

        best_match = None
        best_score = 0

        for cluster_key in clusters:
            cluster_words = set(cluster_key.split("|"))
            overlap = len(key_words & cluster_words)
            score = overlap / max(len(key_words | cluster_words), 1)
            if score > best_score and score > 0.3:
                best_match = cluster_key
                best_score = score

        if best_match:
            clusters[best_match].append(story)
        else:
            cluster_key = "|".join(sorted(key_words)[:8])
            clusters[cluster_key].append(story)

    return clusters


def _get_seasonal_boost(keyword_text):
    """
    Get a seasonal boost score based on current month.
    Food trends are highly seasonal (Ramadan, Christmas, summer).
    """
    current_month = datetime.utcnow().month
    seasonal_keywords = config.SEASONAL_BOOSTS.get(current_month, [])
    text_lower = keyword_text.lower()

    boost = 0.0
    for seasonal_kw in seasonal_keywords:
        if seasonal_kw.lower() in text_lower:
            boost += 15.0
            break

    return boost


def _calculate_spike_score(cluster_stories, conn):
    """
    Calculate a spike score for a cluster of stories.
    Higher score = more newsworthy / trending.
    Enhanced with food-specific intelligence.
    """
    score = 0.0
    factors = []

    # Factor 1: Number of sources covering this story
    unique_sources = set(s["source"] for s in cluster_stories)
    source_count = len(unique_sources)
    score += source_count * 15
    factors.append(f"{source_count} sources")

    # Factor 2: Multiple source types (RSS + NewsAPI + YouTube + Trends = stronger signal)
    source_types = set(s.get("source_type", "unknown") for s in cluster_stories)
    if len(source_types) > 1:
        score += len(source_types) * 12
        factors.append(f"{len(source_types)} source types")

    # Factor 3: Recency Ã¢â‚¬â€ stories from last 2 hours score higher
    now = datetime.utcnow()
    for story in cluster_stories:
        pub = story.get("published_at", now)
        if isinstance(pub, datetime):
            hours_old = (now - pub).total_seconds() / 3600
            if hours_old < 2:
                score += 20
                factors.append("< 2h old")
            elif hours_old < 6:
                score += 10

    # Factor 4: Google Trends rising indicator
    for story in cluster_stories:
        if story.get("is_rising"):
            score += 25
            factors.append("trending on Google")
            break

    # Factor 5: Trend velocity bonus (how fast it's growing; unique to this app!)
    for story in cluster_stories:
        velocity = story.get("velocity", 0)
        if velocity > 1.0:
            score += velocity * 10
            factors.append(f"velocity: {velocity:.1f}x")
            break

    # Factor 6: High-value food keywords
    high_value = getattr(config, "HIGH_VALUE_KEYWORDS", [])
    for story in cluster_stories:
        title_lower = story["title"].lower()
        for hvk in high_value:
            if hvk in title_lower:
                score += 15
                factors.append(f"high-value: {hvk}")
                break
        break  # Only check first story to avoid over-counting

    # Factor 7: YouTube video source (videos = strong viral signal for recipes)
    if any(s.get("source_type") == "youtube" for s in cluster_stories):
        score += 10
        factors.append("YouTube video found")

    # Factor 8: Seasonal relevance boost
    combined_titles = " ".join(s["title"] for s in cluster_stories)
    seasonal_pts = _get_seasonal_boost(combined_titles)
    if seasonal_pts > 0:
        score += seasonal_pts
        current_month = datetime.utcnow().strftime("%B")
        factors.append(f"seasonal ({current_month})")

    # Factor 9: Keyword baseline spike check
    for story in cluster_stories:
        kw = story.get("matched_keyword", "")
        if kw:
            baseline_avg, samples = get_keyword_baseline(conn, kw)
            if samples > 0 and baseline_avg > 0:
                current_mentions = len(cluster_stories)
                ratio = current_mentions / baseline_avg
                if ratio >= config.SPIKE_THRESHOLD:
                    score += ratio * 10
                    factors.append(f"keyword spike {ratio:.1f}x")

    # Factor 10: Brand keywords get a bonus (el mordjene, cebon)
    brand_kws = getattr(config, "BRAND_KEYWORDS", [])
    for story in cluster_stories:
        title_lower = story["title"].lower()
        for bk in brand_kws:
            if bk.lower() in title_lower:
                score += 20
                factors.append(f"brand mention: {bk}")
                break
        break

    return round(score, 1), factors


def _is_excluded(text):
    """Check if text contains any exclusion keywords."""
    text_lower = text.lower()
    for kw in getattr(config, "EXCLUDE_KEYWORDS", []):
        if kw.lower() in text_lower:
            return True
    return False


def _normalize_topic_label(title, matched_keyword=""):
    title = (title or "").strip()
    matched_keyword = (matched_keyword or "").strip()
    lower = title.lower()
    if lower.startswith("rising search:"):
        cleaned = title.split(":", 1)[1].strip()
        return matched_keyword or cleaned or title
    return title

def _recent_topic_penalty(title, keyword, recent_topics):
    """Down-rank over-covered topic families so discovery stays broader."""
    title_lower = (title or "").lower()
    keyword_lower = (keyword or "").lower()
    penalty = 0

    for recent_title, recent_keywords, _published_at in recent_topics:
        haystack = f"{recent_title} {recent_keywords}".lower()
        if keyword_lower and keyword_lower in haystack:
            penalty += 6
        elif title_lower and any(token in haystack for token in title_lower.split() if len(token) > 4):
            penalty += 3

    max_penalty = int(getattr(config, "RECENT_TOPIC_REPEAT_PENALTY", 12))
    return min(penalty, max_penalty)



def detect_spikes(all_stories, trends_data=None):
    """
    Main detection function.
    Takes all stories and returns ranked trending topics with spike scores.
    Includes duplicate content detection against already-published articles.
    """
    conn = get_connection()

    # Merge trends data into stories format
    combined = list(all_stories)
    if trends_data:
        for trend in trends_data:
            if trend.get("is_rising"):
                combined.append({
                    "title": trend["keyword"],
                    "summary": f"Topic signal detected for '{trend['keyword']}' from trend monitoring.",
                    "url": f"https://trends.google.com/trends/explore?q={trend['keyword'].replace(' ', '+')}",
                    "source": trend.get("source", "Google Trends"),
                    "source_type": "trends",
                    "matched_keyword": trend["keyword"],
                    "published_at": trend.get("recorded_at", datetime.utcnow()),
                    "story_hash": hashlib.sha256(trend["keyword"].encode()).hexdigest()[:16],
                    "is_rising": True,
                    "velocity": trend.get("velocity", 0),
                })

    # Exclusion filter
    filtered = []
    excluded_count = 0
    for story in combined:
        title = story.get("title", "")
        keyword = story.get("matched_keyword", "")
        if _is_excluded(title) or _is_excluded(keyword):
            excluded_count += 1
            continue
        filtered.append(story)

    if excluded_count > 0:
        logger.info(f"Spike Detector: Excluded {excluded_count} irrelevant stories")
    combined = filtered

    # Filter out already-seen stories
    new_stories = []
    for story in combined:
        if not is_story_seen(conn, story["story_hash"], config.DEDUP_WINDOW_HOURS):
            new_stories.append(story)
            add_story(conn, story["story_hash"], story["title"],
                      story["source"], story.get("url", ""),
                      story.get("matched_keyword", ""))

    if not new_stories:
        logger.info("Spike Detector: No new stories found")
        conn.close()
        return []

    logger.info(f"Spike Detector: Processing {len(new_stories)} new stories")

    # Record keyword mentions for baseline tracking
    keyword_counts = defaultdict(int)
    for story in new_stories:
        kw = story.get("matched_keyword", "")
        if kw:
            keyword_counts[kw] += 1
    for kw, count in keyword_counts.items():
        record_keyword_mention(conn, kw, "combined", count)

    # Cluster related stories
    clusters = _cluster_stories(new_stories)
    recent_topics = get_recent_published_topics(
        conn,
        limit=int(getattr(config, "RECENT_TOPIC_REPEAT_WINDOW", 12))
    )


    # Score each cluster
    trending_topics = []
    min_score = getattr(config, "SPIKE_MIN_SCORE", 30)
    for cluster_key, cluster_stories_list in clusters.items():
        score, factors = _calculate_spike_score(cluster_stories_list, conn)

        if score >= min_score:
            best_story = max(cluster_stories_list, key=lambda s: len(s["title"]))

            # INTELLIGENCE: Check if we have already published this topic family
            if getattr(config, "CHECK_EXISTING_CONTENT", True):
                is_dup, dup_match, dup_score = is_topic_already_covered(
                    conn, best_story["title"],
                    threshold=getattr(config, "DUPLICATE_SIMILARITY_THRESHOLD", 0.4)
                )
                if is_dup:
                    logger.info(
                        f"  Skipping duplicate topic: '{best_story['title'][:60]}' "
                        f"(similar to '{dup_match[:60]}', score: {dup_score:.2f})"
                    )
                    continue

            repeat_penalty = _recent_topic_penalty(
                best_story["title"],
                best_story.get("matched_keyword", ""),
                recent_topics,
            )
            if repeat_penalty:
                score = max(0, score - repeat_penalty)
                factors.append(f"repeat penalty -{repeat_penalty}")
                if score < min_score:
                    continue


            trending_topics.append({
                "topic": _normalize_topic_label(best_story["title"], best_story.get("matched_keyword", "")),
                "score": score,
                "factors": factors,
                "stories": cluster_stories_list,
                "sources": list(set(s["source"] for s in cluster_stories_list)),
                "top_url": best_story.get("url", ""),
                "matched_keyword": best_story.get("matched_keyword", ""),
                "story_count": len(cluster_stories_list),
            })

    # Sort by score (highest first)
    trending_topics.sort(key=lambda x: x["score"], reverse=True)

    conn.close()
    logger.info(f"Spike Detector: Identified {len(trending_topics)} trending topics")
    return trending_topics

