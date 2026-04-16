"""
Telegram Bot — Sends formatted notifications with interactive buttons.
Handles both sending alerts and receiving commands.
Uses raw requests (no python-telegram-bot dependency).
"""
import logging
import re
import json
import requests

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import config

logger = logging.getLogger(__name__)


def _get_base_url():
    """Build Telegram API URL."""
    token = config.TELEGRAM_BOT_TOKEN
    if not token:
        print("ERROR: TELEGRAM_BOT_TOKEN is not set!")
        logger.error("TELEGRAM_BOT_TOKEN is not set!")
        return None
    return f"https://api.telegram.org/bot{token}"


def send_trending_alert(topic):
    """Send a rich trending topic alert to Telegram with action buttons."""
    score = topic.get("score", 0)
    factors = topic.get("factors", [])
    sources = topic.get("sources", [])
    top_url = topic.get("top_url", "")
    story_count = topic.get("story_count", 1)

    if score >= 80:
        fire = "🔥🔥🔥"
    elif score >= 50:
        fire = "🔥🔥"
    else:
        fire = "🔥"

    lines = [
        f"{fire} TRENDING: {topic['topic']}",
        "━" * 30,
        f"📊 Score: {score} | {story_count} source{'s' if story_count > 1 else ''}",
        f"📰 Sources: {', '.join(sources[:5])}",
        f"🏷️ Keyword: {topic.get('matched_keyword', 'N/A')}",
        "",
        "📝 Why it's trending:",
    ]

    for f in factors[:5]:
        lines.append(f"  • {f}")

    if top_url:
        lines.append(f"\n🔗 Source: {top_url}")

    stories = topic.get("stories", [])
    if stories:
        lines.append("\n📰 Coverage:")
        for s in stories[:3]:
            source_name = s.get("source", "Unknown")
            title = s.get("title", "")[:80]
            url = s.get("url", "")
            lines.append(f"  • [{source_name}] {title}")
            if url:
                lines.append(f"    {url}")

    message = "\n".join(lines)

    story_hash = topic.get("story_hash")
    if not story_hash and topic.get("stories"):
        story_hash = topic["stories"][0].get("story_hash")

    cb_data = f"write_{story_hash[:40]}" if story_hash else "write_article"

    keyboard = {
        "inline_keyboard": [
            [
                {"text": "✍️ Generate Article", "callback_data": cb_data},
                {"text": "🚫 Ignore", "callback_data": "ignore"},
            ]
        ]
    }
    return _send_message(message, reply_markup=keyboard)


def send_simple_message(text, reply_markup=None):
    """Send a simple text message."""
    return _send_message(text, reply_markup=reply_markup)


def send_pending_reminder(title):
    """Send a reminder that an article is pending review."""
    text = f"⚠️ An article is already pending review: '{title}'\n\nPlease ✅ Approve or 🗑️ Reject it before generating a new one."
    keyboard = {
        "inline_keyboard": [
            [{"text": "📋 Show pending article", "callback_data": "show_pending"}],
            [{"text": "🗑️ Clear pending", "callback_data": "clear_pending"}],
        ]
    }
    return _send_message(text, reply_markup=keyboard)


def send_status_update(status_text):
    """Send a status update about the agent's activity."""
    message = f"🤖 Agent Status\n{'━' * 20}\n{status_text}"
    return _send_message(message)


def send_article_preview(article_data):
    """Send an article preview for human review with approve/reject buttons."""
    title = article_data.get("title", "Untitled")
    meta = article_data.get("meta_description", "")
    slug = article_data.get("slug", "")
    word_count = article_data.get("word_count", 0)
    content_preview = article_data.get("content", "")[:800]

    lines = [
        "📝 ARTICLE READY FOR REVIEW",
        "━" * 30,
        "",
        f"Title: {title}",
        f"Slug: /{slug}",
        f"Meta: {meta}",
        f"Words: {word_count}",
        "",
        "Preview:",
        f"{content_preview}...",
    ]

    message = "\n".join(lines)

    keyboard = {
        "inline_keyboard": [
            [
                {"text": "✅ Approve Draft", "callback_data": "approve"},
                {"text": "🚀 Publish Live", "callback_data": "publish_live"},
            ],
            [
                {"text": "🔄 Regenerate Article", "callback_data": "write_article"},
                {"text": "🗑️ Reject", "callback_data": "reject"},
            ],
        ]
    }

    return _send_message(message, reply_markup=keyboard)


def send_publish_confirmation(post_url, post_title, post_id=None, status="publish"):
    """Send confirmation that an article was published or saved as draft."""
    if status.lower() == "draft":
        status_text = "✅ SAVED AS DRAFT"
        bottom_text = "The post is saved as a draft on your site\\."
    else:
        status_text = "🚀 PUBLISHED LIVE"
        bottom_text = "The post is now live on your site\\."

    message = f"""{status_text}
{'━' * 30}

📄 *Title:* {_escape_md(post_title)}
🔗 [View Post]({post_url})

{bottom_text}"""

    keyboard = None
    if status.lower() == "draft" and post_id:
        keyboard = {
            "inline_keyboard": [
                [{"text": "🚀 Publish Live Now", "callback_data": f"publish_draft_{post_id}"}]
            ]
        }

    return _send_message(message, parse_mode="MarkdownV2", reply_markup=keyboard)


def _escape_md(text):
    """Escape special characters for Telegram MarkdownV2."""
    if not text:
        return ""
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    return text


def send_generating_status(topic_title):
    """Send a status message that an article is being generated."""
    message = f"⏳ Generating article for:\n{topic_title}\n\nThis may take 30-60 seconds..."
    return _send_message(message)


def send_image_preview(image_path, article_title):
    """Send a generated featured image to Telegram for approval."""
    base_url = _get_base_url()
    if not base_url:
        return None

    chat_id = config.TELEGRAM_CHAT_ID
    if not chat_id:
        return None

    caption = f"🖼️ Featured Image Preview\n━━━━━━━━━━━━━━━━━━━━\n{article_title}"

    keyboard = {
        "inline_keyboard": [
            [
                {"text": "✅ Use Image", "callback_data": "approve_image"},
                {"text": "🔄 Regenerate Image", "callback_data": "regenerate_image"},
            ],
            [{"text": "🚫 Skip Image", "callback_data": "skip_image"}],
        ]
    }

    try:
        with open(image_path, "rb") as f:
            files = {"photo": f}
            data = {
                "chat_id": chat_id,
                "caption": caption,
                "reply_markup": json.dumps(keyboard),
            }
            response = requests.post(f"{base_url}/sendPhoto", data=data, files=files, timeout=30)

        result = response.json()
        if result.get("ok"):
            message_id = result["result"]["message_id"]
            logger.info(f"Telegram: Image sent (ID: {message_id})")
            return message_id
        else:
            logger.error(f"Telegram sendPhoto error: {result.get('description', 'Unknown')}")
            return None

    except Exception as e:
        logger.error(f"Telegram image send error: {e}")
        return None


def _send_message(text, parse_mode=None, reply_markup=None):
    """Send a message via Telegram Bot API."""
    base_url = _get_base_url()
    if not base_url:
        print("TELEGRAM ERROR: Cannot send message — bot token not configured")
        return None

    chat_id = config.TELEGRAM_CHAT_ID
    if not chat_id:
        print("TELEGRAM ERROR: Cannot send message — chat ID not configured")
        return None

    payload = {
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": False,
    }
    if parse_mode:
        payload["parse_mode"] = parse_mode
    if reply_markup:
        payload["reply_markup"] = reply_markup

    try:
        response = requests.post(f"{base_url}/sendMessage", json=payload, timeout=15)
        result = response.json()

        if result.get("ok"):
            message_id = result["result"]["message_id"]
            logger.info(f"Telegram: Message sent (ID: {message_id})")
            return message_id
        else:
            error_desc = result.get("description", "Unknown error")
            logger.error(f"Telegram API error: {error_desc}")

            if parse_mode and "parse" in error_desc.lower():
                logger.info("Retrying without markdown formatting...")
                plain_text = re.sub(r'\\(.)', r'\1', text)
                plain_text = re.sub(r'\*([^*]+)\*', r'\1', plain_text)
                return _send_message(plain_text, parse_mode=None)

            return None

    except requests.exceptions.Timeout:
        logger.error("Telegram: Request timed out")
        return None
    except Exception as e:
        logger.error(f"Telegram send error: {e}")
        return None


def get_updates(offset=None):
    """Get new messages/commands sent to the bot."""
    base_url = _get_base_url()
    if not base_url:
        return []

    params = {"timeout": 5}
    if offset:
        params["offset"] = offset

    try:
        response = requests.get(f"{base_url}/getUpdates", params=params, timeout=10)
        result = response.json()
        if result.get("ok"):
            return result.get("result", [])
        return []
    except Exception as e:
        logger.error(f"Telegram getUpdates error: {e}")
        return []


def answer_callback_query(callback_query_id, text=""):
    """Acknowledge a callback query (inline button press)."""
    base_url = _get_base_url()
    if not base_url:
        return False

    payload = {"callback_query_id": callback_query_id}
    if text:
        payload["text"] = text

    try:
        response = requests.post(f"{base_url}/answerCallbackQuery", json=payload, timeout=10)
        return response.json().get("ok", False)
    except Exception as e:
        logger.error(f"answerCallbackQuery error: {e}")
        return False


def test_connection():
    """Test the Telegram bot connection."""
    base_url = _get_base_url()
    if not base_url:
        return False, None

    try:
        response = requests.get(f"{base_url}/getMe", timeout=10)
        result = response.json()
        if result.get("ok"):
            bot_name = result["result"].get("username", "Unknown")
            logger.info(f"Telegram bot connected: @{bot_name}")
            return True, bot_name
        return False, None
    except Exception as e:
        logger.error(f"Telegram connection test failed: {e}")
        return False, None


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    ok, name = test_connection()
    if ok:
        print(f"Bot connected: @{name}")
        mid = send_simple_message("🤖 El-Mordjene Agent is online! This is a test message.")
        if mid:
            print(f"Test message sent (ID: {mid})")
        else:
            print("Failed to send test message")
    else:
        print("Bot connection failed. Check your TELEGRAM_BOT_TOKEN.")
