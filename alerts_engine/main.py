import argparse
import hashlib
import json
import logging
import os
import sys
import time
from datetime import datetime

# Prevent UnicodeEncodeError when printing emojis to standard Windows consoles
if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

import config
from database.db import (
    get_connection, cleanup_old_data, save_topic_to_cache,
    get_topic_from_cache, record_notification, mark_notified,
    record_published_topic, count_published_topics, get_recent_published_topics
)
from sources.rss_monitor import fetch_rss_stories
from sources.trends_monitor import fetch_trending_queries
from sources.youtube_monitor import fetch_youtube_videos
from sources.news_api_monitor import fetch_news_headlines
from detection.spike_detector import detect_spikes
from writer.article_generator import generate_article
from writer.review_assistant import (
    duplicate_risk, build_preapproval_checklist, rankmath_polylang_warnings
)
from publisher.wordpress_client import (
    create_post, update_post_status, test_wordpress_connection
)
import publisher.wordpress_client as wp_client
from publisher.image_handler import generate_featured_image
from notifications.telegram_bot import (
    send_trending_alert, send_simple_message, send_article_preview,
    send_publish_confirmation, send_generating_status, send_image_preview,
    send_pending_reminder, get_updates, answer_callback_query, test_connection
)

# --- Unified Pinterest Integration ---
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "pinterest_engine"))
try:
    from pin_generator import process_new_pin
except ImportError:
    process_new_pin = None

#  Logging Setup 
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL, logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(config.LOG_FILE, encoding="utf-8"),
    ]
)
logger = logging.getLogger("agent")

#  Global State 
STATE_FILE = os.path.join(os.path.dirname(__file__), "agent_state.json")
PUBLISHED_POSTS_FILE = os.path.join(os.path.dirname(__file__), "published_posts.json")

def append_latest_published_post(title, slug, url):
    """Append a newly published article to the internal links registry."""
    if not title or not slug or not url:
        return
        
    posts = {}
    if os.path.exists(PUBLISHED_POSTS_FILE):
        try:
            with open(PUBLISHED_POSTS_FILE, "r", encoding="utf-8") as f:
                posts = json.load(f)
        except Exception as e:
            logger.warning(f"Could not load {PUBLISHED_POSTS_FILE}: {e}")
            
    posts[slug] = {
        "url": url,
        "anchor": title
    }
    
    try:
        with open(PUBLISHED_POSTS_FILE, "w", encoding="utf-8") as f:
            json.dump(posts, f, indent=4, ensure_ascii=False)
        logger.info(f"Appended '{title}' to internal links registry.")
    except Exception as e:
        logger.error(f"Failed to save {PUBLISHED_POSTS_FILE}: {e}")


def _load_state():
    """Load agent state from disk."""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "pending_article": None,
        "pending_topic": None,
        "pending_image_paths": None,
        "last_scan": None,
        "scan_count": 0,
        "total_articles": 0,
        "generated_count": 0,
        "generated_words_total": 0,
        "telegram_offset": None,
    }


def _save_state(state):
    """Save agent state to disk."""
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(state, f, indent=2, default=str)
    except Exception as e:
        logger.error(f"Failed to save state: {e}")


# 
#                         SCAN PIPELINE
# 

def run_scan(state):
    """Execute the full scan  detect  alert pipeline."""
    logger.info("=" * 60)
    logger.info(" Starting scan cycle...")
    logger.info("=" * 60)

    conn = get_connection()
    cleanup_old_data(conn)
    conn.close()

    #  Step 1: Collect from all sources 
    logger.info(" Phase 1: Collecting from sources...")
    all_stories = []
    trends_data = []

    # RSS Feeds
    try:
        rss_stories = fetch_rss_stories()
        all_stories.extend(rss_stories)
        logger.info(f"  RSS: {len(rss_stories)} stories")
    except Exception as e:
        logger.error(f"  RSS error: {e}")

    # YouTube
    try:
        yt_stories = fetch_youtube_videos()
        all_stories.extend(yt_stories)
        logger.info(f"  YouTube: {len(yt_stories)} videos")
    except Exception as e:
        logger.error(f"  YouTube error: {e}")

    # NewsAPI
    try:
        news_stories = fetch_news_headlines()
        all_stories.extend(news_stories)
        logger.info(f"  NewsAPI: {len(news_stories)} stories")
    except Exception as e:
        logger.error(f"  NewsAPI error: {e}")

    # Google Trends
    try:
        trends_data = fetch_trending_queries()
        logger.info(f"  Trends: {len(trends_data)} data points, "
                     f"{sum(1 for t in trends_data if t.get('is_rising'))} rising")
    except Exception as e:
        logger.error(f"  Trends error: {e}")

    logger.info(f" Total raw stories: {len(all_stories)}")

    if not all_stories and not trends_data:
        logger.info("No stories or trends found this cycle.")
        state["last_scan"] = datetime.utcnow().isoformat()
        state["scan_count"] = state.get("scan_count", 0) + 1
        return []

    #  Step 2: Detect spikes 
    logger.info(" Phase 2: Detecting spikes...")
    trending_topics = detect_spikes(all_stories, trends_data)
    logger.info(f" Found {len(trending_topics)} trending topics")

    #  Step 3: Send alerts 
    if trending_topics:
        logger.info(" Phase 3: Sending Telegram alerts...")
        conn = get_connection()
        max_topics = int(getattr(config, "MAX_ALERT_TOPICS_PER_SCAN", 3))
        for topic in trending_topics[:max_topics]:
            # Cache topic for later article generation
            story_hash = None
            for s in topic.get("stories", []):
                story_hash = s.get("story_hash")
                if story_hash:
                    break
            if not story_hash:
                story_hash = hashlib.sha256(
                    topic["topic"].encode()
                ).hexdigest()[:16]

            topic["story_hash"] = story_hash
            save_topic_to_cache(conn, story_hash, topic)

            msg_id = send_trending_alert(topic)
            if msg_id:
                record_notification(conn, story_hash, msg_id)
                mark_notified(conn, story_hash)
                logger.info(f"   Alert sent: {topic['topic'][:60]}")
            else:
                logger.warning(f"   Alert failed: {topic['topic'][:60]}")

        conn.close()
    else:
        logger.info("No trending topics to alert about.")

    state["last_scan"] = datetime.utcnow().isoformat()
    state["scan_count"] = state.get("scan_count", 0) + 1

    return trending_topics


# 
#                      COMMAND HANDLING
# 

def poll_telegram_commands(state, timeout_seconds=60):
    """Poll Telegram for button presses and text commands."""
    logger.info(f" Listening for Telegram commands ({timeout_seconds}s)...")
    start_time = time.time()
    offset = state.get("telegram_offset")

    while time.time() - start_time < timeout_seconds:
        try:
            updates = get_updates(offset=offset)

            for update in updates:
                offset = update["update_id"] + 1
                state["telegram_offset"] = offset

                # Handle callback queries (inline button presses)
                callback = update.get("callback_query")
                if callback:
                    _handle_callback(callback, state)
                    continue

                # Handle text messages
                message = update.get("message", {})
                text = message.get("text", "")

                if text.startswith("/status"):
                    _handle_status_command(state)
                elif text.startswith("/scan"):
                    send_simple_message(" Starting manual scan...")
                    run_scan(state)
                elif text.startswith("/help"):
                    _handle_help_command()
                elif text.startswith("/refresh"):
                    _handle_refresh_command()

        except Exception as e:
            logger.error(f"Telegram polling error: {e}")

        time.sleep(2)

    _save_state(state)


def _handle_callback(callback, state):
    """Handle inline button presses from Telegram."""
    data = callback.get("data", "")
    callback_id = callback.get("id", "")

    logger.info(f"  Button pressed: {data}")

    # Acknowledge the callback
    answer_callback_query(callback_id, "Processing...")

    #  Generate Article 
    if data.startswith("write_"):
        _handle_write_article(data, state)

    #  Approve (save as draft) 
    elif data == "approve":
        _handle_approve(state, status="draft")

    #  Publish Live 
    elif data == "publish_live":
        _handle_approve(state, status="publish")

    #  Reject 
    elif data == "reject":
        state["pending_article"] = None
        state["pending_topic"] = None
        state["pending_image_paths"] = None
        _save_state(state)
        send_simple_message(" Article rejected and cleared.")

    #  Ignore trending alert 
    elif data == "ignore":
        send_simple_message(" Ignored.")

    #  Show pending article 
    elif data == "show_pending":
        if state.get("pending_article"):
            send_article_preview(state["pending_article"])
        else:
            send_simple_message("No pending article.")

    #  Clear pending 
    elif data == "clear_pending":
        state["pending_article"] = None
        state["pending_topic"] = None
        state["pending_image_paths"] = None
        _save_state(state)
        send_simple_message(" Pending article cleared.")

    #  Publish draft from Telegram 
    elif data.startswith("publish_draft_"):
        post_id = data.replace("publish_draft_", "")
        try:
            post_id = int(post_id)
            publish_result = update_post_status(post_id, "publish")
            if publish_result and isinstance(publish_result, dict):
                url = publish_result.get("link")
                title = publish_result.get("title", f"Article {post_id}")
                slug = publish_result.get("slug", f"post-{post_id}")
                append_latest_published_post(title, slug, url)
                send_simple_message(f" Post published live!\n{url}")
            elif publish_result and isinstance(publish_result, str):
                send_simple_message(f" Post published live!\n{publish_result}")
            else:
                send_simple_message(f" Failed to publish post {post_id}")
        except Exception as e:
            send_simple_message(f" Error publishing: {e}")


def _handle_write_article(data, state):
    """Handle the 'Generate Article' button press."""
    if state.get("pending_article"):
        send_pending_reminder(state["pending_article"].get("title", "Unknown"))
        return

    story_hash = data.replace("write_", "").replace("write_article", "")

    conn = get_connection()
    topic = get_topic_from_cache(conn, story_hash) if story_hash else None
    conn.close()

    if not topic:
        send_simple_message(" Topic data not found. It may have expired. Run a new scan first.")
        return

    # Cannibalization guard (warning-only)
    conn = get_connection()
    try:
        is_dup, dup_msg = duplicate_risk(conn, topic.get("topic", ""), threshold=0.35)
    finally:
        conn.close()

    if is_dup:
        send_simple_message(
            " Duplicate-risk warning:\n"
            + dup_msg
            + "\nConsider refreshing the old page instead of publishing a new URL."
        )

    send_generating_status(topic.get("topic", "Unknown topic"))

    try:
        article = generate_article(topic)
    except Exception as e:
        logger.error(f"Article generation error: {e}")
        send_simple_message(f" Article generation failed: {str(e)[:200]}")
        return

    if not article:
        send_simple_message(" Article generation failed. Check logs for details.")
        return

    article["matched_keyword"] = topic.get("matched_keyword", "")

    # Status dashboard stats
    state["generated_count"] = int(state.get("generated_count", 0)) + 1
    state["generated_words_total"] = int(state.get("generated_words_total", 0)) + int(article.get("word_count", 0))

    checklist = build_preapproval_checklist(article, topic, duplicate_warning=(dup_msg if is_dup else None))
    send_simple_message(" " + checklist)

    try:
        source_url = topic.get("top_url", "")
        webp_path, jpg_path = generate_featured_image(article["title"], source_url=source_url)
        if webp_path and jpg_path:
            state["pending_image_paths"] = {"webp": webp_path, "jpg": jpg_path}
            send_image_preview(jpg_path, article["title"])
        else:
            state["pending_image_paths"] = None
    except Exception as e:
        logger.warning(f"Image generation failed: {e}")
        state["pending_image_paths"] = None

    state["pending_article"] = article
    state["pending_topic"] = topic
    _save_state(state)
    send_article_preview(article)


def _handle_approve(state, status="draft"):
    """Handle article approval (draft or publish)."""
    article = state.get("pending_article")
    if not article:
        send_simple_message(" No pending article to approve.")
        return

    policy_checks = article.get("policy_checks") or {}
    if status == "publish" and policy_checks.get("block_publish"):
        warnings = policy_checks.get("warnings") or ["Sourcing or quality guard blocked direct publish."]
        send_simple_message(" Publish blocked by quality guard:\n- " + "\n- ".join(warnings[:5]))
        return

    consistency_warnings = rankmath_polylang_warnings(article)
    if consistency_warnings:
        send_simple_message(" Pre-publish checks:\n- " + "\n- ".join(consistency_warnings[:5]))

    image_path = None
    image_paths = state.get("pending_image_paths")
    if image_paths:
        image_path = image_paths.get("jpg") or image_paths.get("webp")

    send_simple_message(f" Publishing to WordPress as {status}...")

    try:
        result = create_post(article, featured_image_path=image_path, status=status)
    except Exception as e:
        send_simple_message(f" Publish error: {e}")
        return

    if result:
        post_id = result.get("post_id")
        post_url = result.get("post_url", "")

        conn = get_connection()
        record_published_topic(
            conn,
            article.get("title", ""),
            article.get("slug", ""),
            ",".join(article.get("tags", []))
        )
        conn.close()
        
        if status == "publish":
            append_latest_published_post(article.get("title", ""), article.get("slug", ""), post_url)
            
            # --- START PINTEREST FLOW ---
            if process_new_pin:
                try:
                    # Pick a default board or use a keyword-based one
                    board_id = os.getenv("BOARD_SWEETS_TRENDS") 
                    process_new_pin(
                        title=article["title"],
                        slug=article["slug"],
                        url=post_url,
                        description=article.get("excerpt", article["title"]),
                        board_id=board_id
                    )
                    send_simple_message("🎨 Premium Pinterest Pin successfully generated and published via Bridge Page!")
                except Exception as e:
                    logger.error(f"Pinterest delivery failed: {e}")
                    send_simple_message(f"⚠️ Pinterest Pin generation failed: {e}")
            # --- END PINTEREST FLOW ---

        send_publish_confirmation(post_url, article["title"], post_id=post_id, status=status)

        state["total_articles"] = state.get("total_articles", 0) + 1
        state["pending_article"] = None
        state["pending_topic"] = None
        state["pending_image_paths"] = None
        _save_state(state)

        logger.info(f" Article published: {article['title']} (ID: {post_id})")
    else:
        error_msg = wp_client.LAST_PUBLISH_ERROR or "Unknown error"
        send_simple_message(f" Publish failed: {error_msg}")


def _handle_status_command(state):
    """Send agent status summary."""
    generated_count = int(state.get("generated_count", 0))
    avg_words = int(state.get("generated_words_total", 0) / max(generated_count, 1)) if generated_count else 0

    published_30 = 0
    top_keywords = []
    conn = get_connection()
    try:
        published_30 = count_published_topics(conn, days=30)
        recent = get_recent_published_topics(conn, limit=100)
        kw_counts = {}
        for _, kws, _ in recent:
            for kw in [k.strip().lower() for k in (kws or "").split(",") if k.strip()]:
                kw_counts[kw] = kw_counts.get(kw, 0) + 1
        top_keywords = sorted(kw_counts.items(), key=lambda x: x[1], reverse=True)[:5]
    finally:
        conn.close()

    lines = [
        f" Scans completed: {state.get('scan_count', 0)}",
        f" Articles published (all-time): {state.get('total_articles', 0)}",
        f" Published last 30 days: {published_30}",
        f" Drafts generated: {generated_count}",
        f" Avg generated words: {avg_words if avg_words else 'N/A'}",
        f" Last scan: {state.get('last_scan', 'Never')}",
        f" Pending article: {'Yes' if state.get('pending_article') else 'No'}",
    ]

    if state.get("pending_article"):
        lines.append(f"   Title: {state['pending_article'].get('title', 'Unknown')}")

    if top_keywords:
        lines.append(" Top repeated keywords (recent):")
        for kw, cnt in top_keywords:
            lines.append(f"   - {kw}: {cnt}")

    send_simple_message("\n".join(lines))


def _handle_refresh_command():
    """Show refresh candidates based on older published topics."""
    conn = get_connection()
    try:
        recent = get_recent_published_topics(conn, limit=40)
    finally:
        conn.close()

    if not recent:
        send_simple_message("No published topics found yet for refresh suggestions.")
        return

    # Suggest older entries first for refresh mode.
    tail = list(reversed(recent))[:5]
    lines = [" Refresh suggestions (older published topics):"]
    for title, keywords, published_at in tail:
        lines.append(f"- {published_at[:10]} | {title[:80]}")
        if keywords:
            lines.append(f"  tags: {keywords[:80]}")

    lines.append("Tip: when a new alert is similar to one above, update old URL instead of publishing a new page.")
    send_simple_message("\n".join(lines))


def _handle_help_command():
    """Send help message."""
    help_text = """ El-Mordjene Agent Commands:

/status  Show agent status
/scan  Trigger a manual scan
/help  Show this help message
/refresh  Suggest old posts to refresh

Button actions:
 Generate Article  Create article from trending topic
 Approve Draft  Save as WordPress draft
 Publish Live  Publish immediately
 Regenerate  Generate a new version
 Reject  Discard the article"""
    send_simple_message(help_text)


# 
#                         TEST MODE
# 

def test_connections():
    """Test all API connections."""
    print("\n" + "=" * 60)
    print(" El-Mordjene Agent  Connection Test")
    print("=" * 60)

    results = {}

    # Telegram
    print("\n1  Telegram Bot...")
    ok, name = test_connection()
    results["telegram"] = ok
    if ok:
        print(f"    Connected: @{name}")
        mid = send_simple_message(" El-Mordjene Agent connection test. All systems go!")
        if mid:
            print(f"    Test message sent (ID: {mid})")
        else:
            print("     Connected but couldn't send message. Check TELEGRAM_CHAT_ID.")
    else:
        print("    Failed. Check TELEGRAM_BOT_TOKEN.")

    # WordPress
    print("\n2  WordPress...")
    ok = test_wordpress_connection()
    results["wordpress"] = ok
    if ok:
        print("    Connected")
    else:
        print("    Failed. Check WP_BASE_URL, WP_USERNAME, WP_APP_PASSWORD.")

    # Gemini
    print("\n3  Gemini API...")
    try:
        from gemini_client import generate_content_with_fallback
        response = generate_content_with_fallback(
            model=config.GEMINI_MODEL,
            contents="Reply with exactly: CONNECTED"
        )
        if "CONNECTED" in response.text.upper():
            print(f"    Connected (model: {config.GEMINI_MODEL})")
            results["gemini"] = True
        else:
            print(f"    Connected but unexpected response")
            results["gemini"] = True
    except Exception as e:
        print(f"    Failed: {e}")
        results["gemini"] = False

    # RSS Feeds
    print("\n4  RSS Feeds...")
    try:
        stories = fetch_rss_stories()
        print(f"    Fetched {len(stories)} stories from {len(config.RSS_FEEDS)} feeds")
        results["rss"] = True
        if stories:
            print(f"    Sample: {stories[0]['title'][:80]}")
    except Exception as e:
        print(f"    Failed: {e}")
        results["rss"] = False

    # YouTube (optional)
    print("\n5  YouTube API...")
    if config.YOUTUBE_API_KEY:
        try:
            videos = fetch_youtube_videos()
            print(f"    Found {len(videos)} videos")
            results["youtube"] = True
        except Exception as e:
            print(f"    Failed: {e}")
            results["youtube"] = False
    else:
        print("     Skipped (no YOUTUBE_API_KEY configured)")
        results["youtube"] = None

    # NewsAPI (optional)
    print("\n6  NewsAPI...")
    if config.NEWS_API_KEY:
        try:
            headlines = fetch_news_headlines()
            print(f"    Found {len(headlines)} headlines")
            results["newsapi"] = True
        except Exception as e:
            print(f"    Failed: {e}")
            results["newsapi"] = False
    else:
        print("     Skipped (no NEWS_API_KEY configured)")
        results["newsapi"] = None

    # Summary
    print("\n" + "=" * 60)
    passed = sum(1 for v in results.values() if v is True)
    failed = sum(1 for v in results.values() if v is False)
    skipped = sum(1 for v in results.values() if v is None)
    print(f" {passed} passed |  {failed} failed |  {skipped} skipped")
    print("=" * 60 + "\n")

    return failed == 0


# 
#                           MAIN
# 

def main():
    parser = argparse.ArgumentParser(
        description="El-Mordjene News Agent  Automated food trend detection and article generation"
    )
    parser.add_argument("--test", action="store_true", help="Test all API connections")
    parser.add_argument("--once", action="store_true", help="Single scan cycle (for cron/CI)")
    parser.add_argument("--listen", action="store_true", help="Listen-only mode (no scanning)")
    args = parser.parse_args()

    state = _load_state()

    if args.test:
        success = test_connections()
        sys.exit(0 if success else 1)

    if args.once:
        logger.info("Running single scan cycle (--once mode)")

        # Pre-scan: check for pending commands
        poll_telegram_commands(state, timeout_seconds=10)

        # Run scan
        topics = run_scan(state)

        # Post-scan: listen for button presses
        if topics:
            logger.info("Waiting for Telegram commands after scan...")
            poll_telegram_commands(state, timeout_seconds=420)

        _save_state(state)
        logger.info("Single scan complete. Exiting.")
        return

    if args.listen:
        logger.info("Listen-only mode (--listen). No scanning.")
        send_simple_message(" El-Mordjene Agent is online (listen mode).")
        while True:
            try:
                poll_telegram_commands(state, timeout_seconds=300)
                _save_state(state)
            except KeyboardInterrupt:
                logger.info("Interrupted. Saving state and exiting.")
                _save_state(state)
                break

    # Default: continuous loop
    logger.info("=" * 60)
    logger.info(" El-Mordjene Agent starting (continuous mode)")
    logger.info(f"   Scan interval: {config.SCAN_INTERVAL_MINUTES} minutes")
    logger.info("=" * 60)

    send_simple_message(
        f" El-Mordjene Agent is online!\n"
        f"Scanning every {config.SCAN_INTERVAL_MINUTES} min.\n"
        f"Use /help for commands."
    )

    while True:
        try:
            # Run scan
            run_scan(state)
            _save_state(state)

            # Listen for commands until next scan
            logger.info(f" Next scan in {config.SCAN_INTERVAL_MINUTES} minutes. Listening for commands...")
            poll_telegram_commands(state, timeout_seconds=config.SCAN_INTERVAL_MINUTES * 60)
            _save_state(state)

        except KeyboardInterrupt:
            logger.info("Interrupted. Saving state and exiting.")
            _save_state(state)
            send_simple_message(" El-Mordjene Agent shutting down.")
            break
        except Exception as e:
            logger.error(f"Agent loop error: {e}", exc_info=True)
            time.sleep(60)


if __name__ == "__main__":
    main()
