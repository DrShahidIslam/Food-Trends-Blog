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
    record_published_topic, get_recent_published_topics,
    is_topic_already_covered
)
from writer.article_generator import generate_article
try:
    from writer.quality_gate import run_el_quality_gate
except ImportError:
    run_el_quality_gate = None
from publisher.wordpress_client import (
    create_post, test_wordpress_connection
)
from publisher.image_handler import generate_featured_image
from sources.rss_monitor import fetch_rss_stories
from sources.news_api_monitor import fetch_news_headlines
from sources.trends_monitor import fetch_trending_queries
from sources.pinterest_trends_monitor import fetch_pinterest_trends

# --- Unified Pinterest Integration ---
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "pinterest_engine"))
try:
    from pin_generator import process_new_pin
except ImportError:
    process_new_pin = None

# Configure logging
logging.basicConfig(
    level=getattr(config, "LOG_LEVEL", "INFO"),
    format='%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
    handlers=[logging.StreamHandler(), logging.FileHandler(config.LOG_FILE, encoding='utf-8')]
)
logger = logging.getLogger("agent")

STATE_FILE = "agent_state.json"
PUBLISHED_POSTS_FILE = os.path.join(os.path.dirname(__file__), "published_posts.json")

def _load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f: return json.load(f)
        except: pass
    return {"last_scan": None, "scan_count": 0, "published_today": []}

def _save_state(state):
    with open(STATE_FILE, "w") as f: json.dump(state, f, indent=2)

def _load_published_posts():
    if os.path.exists(PUBLISHED_POSTS_FILE):
        try:
            with open(PUBLISHED_POSTS_FILE, "r", encoding="utf-8") as f: return json.load(f)
        except: return {}
    return {}

def append_latest_published_post(title, slug, url):
    """Append a newly published article to the internal links registry."""
    if not title or not slug or not url:
        return
        
    posts = _load_published_posts()
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

def _finish_publication(article, post_id, post_url, state):
    logger.info(f"   Published: {article['title']}")
    logger.info(f"   URL: {post_url}")
    state["last_published_url"] = post_url
    state["published_today"].append({
        "title": article["title"],
        "url": post_url,
        "time": datetime.utcnow().isoformat()
    })
    append_latest_published_post(article["title"], article["slug"], post_url)

def auto_pilot_process(topic, state):
    """Zero-click automation: Generate, Image, and Publish."""
    topic_title = topic.get("topic", "Unknown")
    logger.info(f"🚀 AUTO-PILOT: Processing '{topic_title}'...")
    
    # 1. Generate Article
    try:
        article = generate_article(topic)
        if not article: return False
    except Exception as e:
        logger.error(f"Auto-Pilot generation error: {e}")
        return False

    # 1b. Quality gate (fail-closed): do not publish thin / unlinked / lowercase-title articles
    if run_el_quality_gate is not None:
        try:
            passed, gate_failures, gate_warnings = run_el_quality_gate(article)
        except Exception as e:
            logger.warning(f"Quality gate error (publishing anyway): {e}")
            passed, gate_failures, gate_warnings = True, [], []
        for w in gate_warnings:
            logger.warning(f"Quality gate warning: {w}")
        if not passed:
            for f in gate_failures:
                logger.error(f"Quality gate FAILED: {f}")
            return False

    # 2. Generate Image
    image_path = None
    try:
        source_url = topic.get("top_url", "")
        webp_path, jpg_path = generate_featured_image(article["title"], source_url=source_url)
        image_path = webp_path or jpg_path
    except Exception as e:
        logger.warning(f"Auto-Pilot Image failure: {e}")

    # 3. Publish to WordPress
    try:
        status = config.WP_DEFAULT_STATUS
        result = create_post(article, featured_image_path=image_path, status=status)
        if result:
            post_url = result.get("post_url", "")
            post_id = result.get("post_id")
            
            # Record in DB
            conn = get_connection()
            record_published_topic(conn, article["title"], article["slug"], ",".join(article.get("tags", [])))
            conn.close()
            
            # The Pinterest Flow is now handled by the dedicated Pin Worker (GitHub Action)
            # which reads from topic_queue.json once wp_status is 'done'.
            
            _finish_publication(article, post_id, post_url, state)
            return True
    except Exception as e:
        logger.error(f"Auto-Pilot Publish error: {e}")
        
    return False

def _load_queue():
    queue_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "topic_queue.json")
    if os.path.exists(queue_path):
        try:
            with open(queue_path, "r") as f: return json.load(f)
        except: return []
    return []

def _save_queue(queue):
    queue_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "topic_queue.json")
    with open(queue_path, "w") as f: json.dump(queue, f, indent=2)

def run_scan(state):
    """Perform one full trend scan (Queue-first) and trigger auto-pilot."""
    # PRE-RUN CONNECTION CHECK
    if not test_wordpress_connection():
        logger.error("🛑 ABORTING SCAN: WordPress connection failed. Saving resources.")
        return

    logger.info("=" * 60)
    logger.info(" Starting scan cycle...")
    logger.info("=" * 60)

    max_per_run = int(config.POSTS_PER_RUN or 2)
    published_count = 0
    
    # 1. Check Topic Queue First
    queue = _load_queue()
    pending = [t for t in queue if t.get("wp_status") == "pending"]
    pending.sort(key=lambda x: x.get("priority", 99))

    if pending:
        logger.info(f"Found {len(pending)} pending topics in queue.")
        conn = get_connection()
        for topic in pending:
            if published_count >= max_per_run: break
            
            # CHECK FOR EXISTING CONTENT FIRST
            is_covered, match_title, score = is_topic_already_covered(conn, topic["topic"], threshold=0.6)
            if is_covered:
                logger.info(f"Topic '{topic['topic']}' already covered by '{match_title}' (Score: {score:.2f}). Skipping generation.")
                topic["wp_status"] = "done"
                # Find the URL for the existing post
                # We'll look in published_posts.json or db
                published_list = _load_published_posts()
                existing_url = next((p["url"] for p in published_list.values() if p.get("anchor") == match_title), "")
                topic["wp_url"] = existing_url
                topic["published_at"] = datetime.utcnow().isoformat()
                topic["note"] = f"Auto-linked to existing: {match_title}"
                _save_queue(queue)
                continue

            # Prepare topic for auto-pilot
            try:
                if auto_pilot_process(topic, state):
                    topic["wp_status"] = "done"
                    topic["wp_url"] = state.get("last_published_url", "")
                    topic["published_at"] = datetime.utcnow().isoformat()
                    published_count += 1
                else:
                    # Increment retry or mark as failed
                    retries = topic.get("retries", 0) + 1
                    topic["retries"] = retries
                    if retries >= 3:
                        topic["wp_status"] = "failed"
                        logger.warning(f"Topic '{topic['topic']}' failed after 3 attempts. Marking as failed.")
            except Exception as e:
                logger.error(f"Critical error processing queue topic: {e}")
            
            _save_queue(queue) # Update queue state
            if published_count >= max_per_run: break
            time.sleep(10)
        conn.close()

    if not pending:
        logger.error("PENDING=0 ALERT: topic_queue.json has no pending topics — publisher ran empty. Refill the queue from the Semrush+Trends gate log before the next run.")

    # 2. Aggregated Discovery (RSS, NewsAPI, Google Trends, Pinterest)
    if published_count < max_per_run:
        logger.info(f"Queue empty or limit not reached. Running aggregated discovery... ({published_count}/{max_per_run})")
        
        aggregated_trends = []
        
        # A. Pinterest Trends
        try:
            aggregated_trends.extend(fetch_pinterest_trends())
        except Exception as e:
            logger.warning(f"Discovery: Pinterest failed: {e}")

        # B. RSS Stories
        try:
            rss_stories = fetch_rss_stories()
            for s in rss_stories:
                aggregated_trends.append({
                    "topic": s["title"],
                    "matched_keyword": s["matched_keyword"],
                    "source": s["source"],
                    "top_url": s["url"],
                    "stories": [s]
                })
        except Exception as e:
            logger.warning(f"Discovery: RSS failed: {e}")

        # C. NewsAPI Headlines
        try:
            news_stories = fetch_news_headlines()
            for s in news_stories:
                aggregated_trends.append({
                    "topic": s["title"],
                    "matched_keyword": s["matched_keyword"],
                    "source": s["source"],
                    "top_url": s["url"],
                    "stories": [s]
                })
        except Exception as e:
            logger.warning(f"Discovery: NewsAPI failed: {e}")

        # D. Google Trends
        try:
            google_trends = fetch_trending_queries()
            for t in google_trends:
                if t.get("is_rising"):
                    aggregated_trends.append({
                        "topic": t["keyword"],
                        "matched_keyword": t["keyword"],
                        "source": t["source"],
                        "score": t.get("spike_ratio", 1.0)
                    })
        except Exception as e:
            logger.warning(f"Discovery: Google Trends failed: {e}")

        if aggregated_trends:
            # Sort by score or significance if available
            aggregated_trends.sort(key=lambda x: x.get("score", 1.0), reverse=True)
            
            conn = get_connection()
            for topic in aggregated_trends:
                if published_count >= max_per_run: break
                
                # Deduplicate against queue and cache
                topic_title = topic["topic"].lower()
                if any(q["topic"].lower() == topic_title for q in queue):
                    continue
                
                # Deduplicate against DB
                is_covered, _, _ = is_topic_already_covered(conn, topic["topic"], threshold=0.5)
                if is_covered:
                    continue

                story_hash = hashlib.sha256(topic["topic"].encode()).hexdigest()[:16]
                topic["story_hash"] = story_hash
                save_topic_to_cache(conn, story_hash, topic)

                if auto_pilot_process(topic, state):
                    # NEW: Add to topic queue so Pinterest worker can pin it
                    new_queue_entry = {
                        "topic": topic["topic"],
                        "intent": "trend",
                        "wp_status": "done",
                        "wp_url": state.get("last_published_url", ""),
                        "pin_count": 0,
                        "priority": 20,
                        "source": "Auto-Pilot",
                        "published_at": datetime.utcnow().isoformat()
                    }
                    queue.append(new_queue_entry)
                    _save_queue(queue)
                    
                    published_count += 1
                    time.sleep(10)
            conn.close()

    cleanup_old_data(get_connection())
    state["last_scan"] = datetime.utcnow().isoformat()
    state["scan_count"] += 1
    _save_state(state)
    logger.info(f"Scan complete. Published {published_count} articles.")

def main():
    parser = argparse.ArgumentParser(description="El-Mordjene News Agent (Headless)")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    parser.add_argument("--test", action="store_true", help="Test connections")
    args = parser.parse_args()

    state = _load_state()

    if args.test:
        print("Testing connections...")
        wp_ok = test_wordpress_connection()
        print(f"WordPress: {'OK' if wp_ok else 'FAILED'}")
        # Test Gemini
        from gemini_client import generate_content_with_fallback
        try:
            res = generate_content_with_fallback(model=config.GEMINI_MODEL, contents="Hi")
            print(f"Gemini: OK ({config.GEMINI_MODEL})")
        except Exception as e:
            print(f"Gemini: FAILED ({e})")
        return

    if args.once:
        run_scan(state)
        return

    # Continuous loop
    logger.info(f"Headless agent starting. Interval: {config.SCAN_INTERVAL_MINUTES}m")
    while True:
        try:
            run_scan(state)
            logger.info(f"Sleeping for {config.SCAN_INTERVAL_MINUTES} minutes...")
            time.sleep(config.SCAN_INTERVAL_MINUTES * 60)
        except KeyboardInterrupt:
            break
        except Exception as e:
            logger.error(f"Main loop error: {e}")
            time.sleep(60)

if __name__ == "__main__":
    main()
