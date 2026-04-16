"""
SQLite database for tracking seen stories, keyword baselines, and sent notifications.
Handles deduplication, spike history, and content intelligence.
"""
import sqlite3
import os
import json
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "agent.db")


def get_connection():
    """Get a database connection, creating tables if needed."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    _create_tables(conn)
    return conn


def _create_tables(conn):
    """Create all required tables if they don't exist."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS seen_stories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            story_hash TEXT UNIQUE NOT NULL,
            title TEXT NOT NULL,
            source TEXT,
            url TEXT,
            keywords TEXT,
            first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            notified INTEGER DEFAULT 0,
            article_written INTEGER DEFAULT 0,
            article_published INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS keyword_mentions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            keyword TEXT NOT NULL,
            source TEXT NOT NULL,
            mention_count INTEGER DEFAULT 1,
            recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS notifications_sent (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            story_hash TEXT NOT NULL,
            telegram_message_id TEXT,
            sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS trend_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            keyword TEXT NOT NULL,
            interest_value INTEGER,
            is_rising INTEGER DEFAULT 0,
            recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS topic_cache (
            story_hash TEXT PRIMARY KEY,
            topic_json TEXT NOT NULL,
            recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS published_topics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            slug TEXT,
            keywords TEXT,
            published_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_seen_stories_hash ON seen_stories(story_hash);
        CREATE INDEX IF NOT EXISTS idx_keyword_mentions_keyword ON keyword_mentions(keyword);
        CREATE INDEX IF NOT EXISTS idx_notifications_hash ON notifications_sent(story_hash);
        CREATE INDEX IF NOT EXISTS idx_published_title ON published_topics(title);
    """)
    conn.commit()


def is_story_seen(conn, story_hash, dedup_hours=12):
    """Check if a story has been seen within the deduplication window."""
    cutoff = datetime.utcnow() - timedelta(hours=dedup_hours)
    row = conn.execute(
        "SELECT id FROM seen_stories WHERE story_hash = ? AND first_seen_at > ?",
        (story_hash, cutoff.isoformat())
    ).fetchone()
    return row is not None


def add_story(conn, story_hash, title, source, url, keywords=""):
    """Record a new story in the database."""
    try:
        conn.execute(
            """INSERT OR IGNORE INTO seen_stories (story_hash, title, source, url, keywords)
               VALUES (?, ?, ?, ?, ?)""",
            (story_hash, title, source, url, keywords)
        )
        conn.commit()
    except sqlite3.IntegrityError:
        pass


def mark_notified(conn, story_hash):
    """Mark a story as having been notified about."""
    conn.execute(
        "UPDATE seen_stories SET notified = 1 WHERE story_hash = ?",
        (story_hash,)
    )
    conn.commit()


def record_keyword_mention(conn, keyword, source, count=1):
    """Record a keyword mention for baseline tracking."""
    conn.execute(
        """INSERT INTO keyword_mentions (keyword, source, mention_count)
           VALUES (?, ?, ?)""",
        (keyword, source, count)
    )
    conn.commit()


def get_keyword_baseline(conn, keyword, hours=24):
    """Get the average mention count for a keyword over the past N hours."""
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    row = conn.execute(
        """SELECT AVG(mention_count) as avg_count, COUNT(*) as samples
           FROM keyword_mentions
           WHERE keyword = ? AND recorded_at > ?""",
        (keyword, cutoff.isoformat())
    ).fetchone()
    if row and row["avg_count"]:
        return float(row["avg_count"]), int(row["samples"])
    return 0.0, 0


def record_notification(conn, story_hash, message_id=""):
    """Record that a notification was sent."""
    conn.execute(
        """INSERT INTO notifications_sent (story_hash, telegram_message_id)
           VALUES (?, ?)""",
        (story_hash, str(message_id))
    )
    conn.commit()


def record_trend_snapshot(conn, keyword, interest_value, is_rising=False):
    """Record a Google Trends snapshot."""
    conn.execute(
        """INSERT INTO trend_snapshots (keyword, interest_value, is_rising)
           VALUES (?, ?, ?)""",
        (keyword, interest_value, 1 if is_rising else 0)
    )
    conn.commit()


def save_topic_to_cache(conn, story_hash, topic_dict):
    """Save a trending topic as JSON in the database for later generation."""
    try:
        topic_json = json.dumps(topic_dict, default=str)
        conn.execute(
            """INSERT OR REPLACE INTO topic_cache (story_hash, topic_json)
               VALUES (?, ?)""",
            (story_hash, topic_json)
        )
        conn.commit()
    except Exception as e:
        logger.error(f"Failed to cache topic {story_hash}: {e}")


def get_topic_from_cache(conn, story_hash):
    """Retrieve a trending topic from JSON cache."""
    row = conn.execute(
        "SELECT topic_json FROM topic_cache WHERE story_hash LIKE ?",
        (f"{story_hash}%",)
    ).fetchone()

    if row and row["topic_json"]:
        try:
            return json.loads(row["topic_json"])
        except Exception as e:
            logger.error(f"Failed to parse cached topic {story_hash}: {e}")
    return None


def record_published_topic(conn, title, slug="", keywords=""):
    """Record a published topic to prevent duplicate content."""
    conn.execute(
        """INSERT INTO published_topics (title, slug, keywords) VALUES (?, ?, ?)""",
        (title, slug, keywords)
    )
    conn.commit()


def get_published_titles(conn, limit=50):
    """Get recently published titles for duplicate detection."""
    rows = conn.execute(
        "SELECT title, keywords FROM published_topics ORDER BY published_at DESC LIMIT ?",
        (limit,)
    ).fetchall()
    return [(row["title"], row["keywords"] or "") for row in rows]


def is_topic_already_covered(conn, new_title, threshold=0.4):
    """Check if a topic is too similar to already-published content.

    Uses Jaccard similarity on word sets to detect near-duplicate topics.
    Returns (is_duplicate, closest_match_title, similarity_score).
    """
    published = get_published_titles(conn)
    if not published:
        return False, "", 0.0

    new_words = set(new_title.lower().split())
    stop_words = {"the", "a", "an", "is", "are", "was", "in", "on", "at",
                  "to", "for", "of", "with", "and", "or", "but", "this",
                  "that", "it", "how", "what", "why", "when", "which"}
    new_words -= stop_words

    best_match = ""
    best_score = 0.0

    for pub_title, pub_keywords in published:
        pub_words = set(pub_title.lower().split()) | set(pub_keywords.lower().split())
        pub_words -= stop_words

        if not new_words or not pub_words:
            continue

        intersection = len(new_words & pub_words)
        union = len(new_words | pub_words)
        similarity = intersection / union if union > 0 else 0.0

        if similarity > best_score:
            best_score = similarity
            best_match = pub_title

    return best_score >= threshold, best_match, best_score


def cleanup_old_data(conn, days=7):
    """Remove data older than N days to keep the DB small."""
    cutoff = datetime.utcnow() - timedelta(days=days)
    conn.execute("DELETE FROM keyword_mentions WHERE recorded_at < ?", (cutoff.isoformat(),))
    conn.execute("DELETE FROM trend_snapshots WHERE recorded_at < ?", (cutoff.isoformat(),))

    old_cutoff = datetime.utcnow() - timedelta(days=14)
    conn.execute("DELETE FROM seen_stories WHERE first_seen_at < ?", (old_cutoff.isoformat(),))
    conn.execute("DELETE FROM notifications_sent WHERE sent_at < ?", (old_cutoff.isoformat(),))
    conn.execute("DELETE FROM topic_cache WHERE recorded_at < ?", (old_cutoff.isoformat(),))
    conn.commit()

def count_published_topics(conn, days=30):
    """Count published topics in the last N days."""
    row = conn.execute(
        "SELECT COUNT(*) AS cnt FROM published_topics WHERE published_at >= datetime('now', ?)",
        (f"-{int(days)} days",)
    ).fetchone()
    return int(row["cnt"]) if row and row["cnt"] is not None else 0


def get_recent_published_topics(conn, limit=100):
    """Return recent published topics as (title, keywords, published_at)."""
    rows = conn.execute(
        "SELECT title, keywords, published_at FROM published_topics ORDER BY published_at DESC LIMIT ?",
        (int(limit),)
    ).fetchall()
    return [(r["title"] or "", r["keywords"] or "", r["published_at"] or "") for r in rows]
