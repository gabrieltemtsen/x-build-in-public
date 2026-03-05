"""
main.py — Build in Public automation agent.

Watches GitHub repos → generates threads with Gemini → posts to X.
Also posts daily standalone value tweets and weekly newsletter drafts.
"""

import os
import sys
import logging
import time
import random
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml
from dotenv import load_dotenv

from .github_watcher import get_new_events, get_repo_summary
from .thread_gen import generate_thread_from_event, generate_daily_tweets, generate_newsletter_draft
from .tweet_poster import post_thread, post_single
from .notifier import notify_thread_posted, notify_daily_posted, notify_newsletter_saved, notify_error
from .scheduler import build_scheduler

load_dotenv()

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)
WAT = ZoneInfo("Africa/Lagos")

# --- Load config ---
CONFIG_PATH = Path(__file__).parent.parent / "config" / "config.yaml"
with open(CONFIG_PATH) as f:
    CFG = yaml.safe_load(f)

GH_USERNAME = CFG["github"]["username"]
GH_REPOS = CFG["github"]["repos"]
CHECK_INTERVAL = CFG["github"]["check_interval_minutes"]

NICHE = CFG["content"]["niche"]
TONE = CFG["content"]["tone"]
DAILY_COUNT = CFG["content"]["daily_tweets"]
POSTING_TIMES = CFG["content"]["posting_times_wat"]

DRY_RUN = os.getenv("DRY_RUN", str(CFG["twitter"]["dry_run"])).lower() in ("true", "1", "yes")

NL_ENABLED = os.getenv("BEEHIIV_API_KEY") is not None or CFG["newsletter"]["enabled"]
NL_DAY = CFG["newsletter"]["day"]
NL_TIME = CFG["newsletter"]["time_wat"]
NL_OUTPUT_DIR = Path(CFG["newsletter"]["output_dir"])

# Track recently processed event SHAs to avoid duplicate threads
_posted_shas: set[str] = set()


def check_github_and_post():
    """Check for new GitHub events and post threads."""
    logger.info("🔍 Checking GitHub for new events...")
    try:
        events = get_new_events(GH_USERNAME, GH_REPOS)
        if not events:
            logger.info("No new events.")
            return

        for event in events:
            sha = event.get("sha") or event["url"]
            if sha in _posted_shas:
                logger.info(f"Already posted for {sha}, skipping.")
                continue

            logger.info(f"New event: [{event['repo']}] {event['title']}")
            try:
                thread = generate_thread_from_event(event, NICHE, TONE)
                if not thread:
                    logger.warning("Thread generator returned empty — skipping")
                    continue

                logger.info(f"Generated {len(thread)}-tweet thread for {event['repo']}")
                tweet_ids = post_thread(thread, dry_run=DRY_RUN)

                _posted_shas.add(sha)
                if len(_posted_shas) > 500:
                    # Prune old entries
                    _posted_shas.clear()

                notify_thread_posted(event["repo"], tweet_ids, DRY_RUN)

                # Small delay between threads if multiple events
                time.sleep(2)

            except Exception as e:
                logger.error(f"Failed to generate/post thread for {event['repo']}: {e}")
                notify_error(f"Thread generation [{event['repo']}]", str(e))

    except Exception as e:
        logger.error(f"GitHub check failed: {e}")
        notify_error("GitHub watcher", str(e))


def post_daily_tweets():
    """Generate and post standalone daily value tweets."""
    logger.info("📣 Posting daily tweets...")
    try:
        tweets = generate_daily_tweets(NICHE, TONE, DAILY_COUNT)
        if not tweets:
            logger.warning("No daily tweets generated")
            return

        posted = 0
        for tweet in tweets:
            tid = post_single(tweet, dry_run=DRY_RUN)
            if tid:
                posted += 1
            time.sleep(random.uniform(30, 90))  # space tweets out naturally

        notify_daily_posted(posted, DRY_RUN)
        logger.info(f"✅ Posted {posted} daily tweets")

    except Exception as e:
        logger.error(f"Daily tweets failed: {e}")
        notify_error("Daily tweet generator", str(e))


def generate_newsletter():
    """Generate weekly newsletter draft and save to file."""
    logger.info("📰 Generating weekly newsletter...")
    try:
        repo_summary = get_repo_summary(GH_USERNAME, GH_REPOS)
        # Use last week's GitHub events as context (re-fetch)
        events = get_new_events(GH_USERNAME, GH_REPOS)
        draft = generate_newsletter_draft(repo_summary, events, NICHE)

        NL_OUTPUT_DIR.mkdir(exist_ok=True)
        date_str = datetime.now(WAT).strftime("%Y-%m-%d")
        out_path = NL_OUTPUT_DIR / f"newsletter_{date_str}.md"
        out_path.write_text(draft)
        logger.info(f"Newsletter saved: {out_path}")
        notify_newsletter_saved(str(out_path))

    except Exception as e:
        logger.error(f"Newsletter generation failed: {e}")
        notify_error("Newsletter generator", str(e))


def validate_env():
    required = [
        "X_BEARER_TOKEN", "X_CONSUMER_KEY", "X_CONSUMER_SECRET",
        "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET", "GEMINI_API_KEY",
    ]
    missing = [k for k in required if not os.getenv(k)]
    if missing:
        logger.error(f"❌ Missing env vars: {', '.join(missing)}")
        sys.exit(1)
    logger.info("✅ All required env vars present")


def main():
    validate_env()

    mode = "DRY RUN" if DRY_RUN else "LIVE"
    logger.info(f"🚀 x-build-in-public starting [{mode}]")
    logger.info(f"Watching repos: {GH_REPOS}")
    logger.info(f"Posting times WAT: {POSTING_TIMES}")

    # Run one immediate GitHub check on startup
    check_github_and_post()

    # Build and start scheduler
    scheduler = build_scheduler(
        github_check_fn=check_github_and_post,
        daily_tweet_fn=post_daily_tweets,
        newsletter_fn=generate_newsletter,
        check_interval_minutes=CHECK_INTERVAL,
        posting_times_wat=POSTING_TIMES,
        newsletter_day=NL_DAY,
        newsletter_time_wat=NL_TIME,
        newsletter_enabled=NL_ENABLED,
    )
    scheduler.start()
    logger.info("✅ Scheduler started")

    try:
        while True:
            time.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        logger.info("Scheduler stopped. Bye.")


if __name__ == "__main__":
    main()
