"""
tweet_poster.py — posts tweets and threads to X via Tweepy.
Supports dry_run mode (logs without posting).
"""

import os
import time
import logging
import tweepy

logger = logging.getLogger(__name__)


def _get_client() -> tweepy.Client:
    return tweepy.Client(
        bearer_token=os.environ["X_BEARER_TOKEN"],
        consumer_key=os.environ["X_CONSUMER_KEY"],
        consumer_secret=os.environ["X_CONSUMER_SECRET"],
        access_token=os.environ["X_ACCESS_TOKEN"],
        access_token_secret=os.environ["X_ACCESS_TOKEN_SECRET"],
    )


def post_thread(tweets: list[str], dry_run: bool = True) -> list[str]:
    """
    Post a thread. Returns list of tweet IDs (or mock IDs in dry_run).
    Respects X API rate limits: 0.5s between tweets.
    """
    if not tweets:
        logger.warning("post_thread called with empty list")
        return []

    if dry_run:
        logger.info(f"[DRY RUN] Would post thread ({len(tweets)} tweets):")
        for i, t in enumerate(tweets, 1):
            logger.info(f"  [{i}] {t}")
        return [f"dry_run_{i}" for i in range(len(tweets))]

    client = _get_client()
    tweet_ids = []
    reply_to = None

    for i, text in enumerate(tweets):
        try:
            if reply_to:
                resp = client.create_tweet(text=text, in_reply_to_tweet_id=reply_to)
            else:
                resp = client.create_tweet(text=text)

            tweet_id = resp.data["id"]
            tweet_ids.append(tweet_id)
            reply_to = tweet_id
            logger.info(f"✅ Tweet {i+1}/{len(tweets)} posted: {tweet_id}")
            time.sleep(0.6)  # stay well under rate limit

        except tweepy.TweepyException as e:
            logger.error(f"❌ Failed to post tweet {i+1}: {e}")
            if "Rate limit" in str(e):
                logger.warning("Rate limited — sleeping 60s")
                time.sleep(60)
                # retry once
                try:
                    if reply_to:
                        resp = client.create_tweet(text=text, in_reply_to_tweet_id=reply_to)
                    else:
                        resp = client.create_tweet(text=text)
                    tweet_id = resp.data["id"]
                    tweet_ids.append(tweet_id)
                    reply_to = tweet_id
                    logger.info(f"✅ Tweet {i+1} posted after retry: {tweet_id}")
                except Exception as retry_err:
                    logger.error(f"Retry also failed: {retry_err}")
            break

    return tweet_ids


def post_single(text: str, dry_run: bool = True) -> str | None:
    """Post a single standalone tweet. Returns tweet ID."""
    if dry_run:
        logger.info(f"[DRY RUN] Would tweet: {text}")
        return "dry_run_single"

    client = _get_client()
    try:
        resp = client.create_tweet(text=text)
        tid = resp.data["id"]
        logger.info(f"✅ Tweet posted: {tid}")
        return tid
    except tweepy.TweepyException as e:
        logger.error(f"❌ Failed to post: {e}")
        return None
