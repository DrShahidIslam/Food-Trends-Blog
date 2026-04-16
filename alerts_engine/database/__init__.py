"""Database package — re-exports from db.py for convenience."""
from database.db import (
    get_connection,
    is_story_seen,
    add_story,
    mark_notified,
    record_keyword_mention,
    get_keyword_baseline,
    record_notification,
    record_trend_snapshot,
    save_topic_to_cache,
    get_topic_from_cache,
    record_published_topic,
    get_published_titles,
    is_topic_already_covered,
    cleanup_old_data,
)
