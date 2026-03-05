"""
notifier.py — Telegram notifications for posted threads and errors.
"""

import os
import logging
import requests

logger = logging.getLogger(__name__)


def _send(text: str):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        logger.warning("Telegram creds not set — skipping notification")
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
            timeout=10,
        )
    except Exception as e:
        logger.error(f"Telegram notify failed: {e}")


def notify_thread_posted(repo: str, tweet_ids: list[str], dry_run: bool):
    prefix = "🧪 [DRY RUN] " if dry_run else "🐦 "
    first_id = tweet_ids[0] if tweet_ids else "?"
    url = f"https://x.com/i/web/status/{first_id}" if not dry_run else "(dry run)"
    _send(
        f"{prefix}<b>Thread posted!</b>\n"
        f"Repo: <code>{repo}</code>\n"
        f"Tweets: {len(tweet_ids)}\n"
        f"First: {url}"
    )


def notify_daily_posted(count: int, dry_run: bool):
    prefix = "🧪 [DRY RUN] " if dry_run else "📣 "
    _send(f"{prefix}<b>{count} daily tweet(s) posted</b>")


def notify_newsletter_saved(path: str):
    _send(f"📰 <b>Newsletter draft saved</b>\n<code>{path}</code>")


def notify_error(context: str, error: str):
    _send(f"❌ <b>Error in x-build-in-public</b>\nContext: {context}\n<code>{error}</code>")
