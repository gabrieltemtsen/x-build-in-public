"""
scheduler.py — APScheduler config for all posting jobs.
"""

import logging
import random
from datetime import datetime
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)
WAT = ZoneInfo("Africa/Lagos")


def build_scheduler(
    github_check_fn,
    daily_tweet_fn,
    newsletter_fn,
    check_interval_minutes: int,
    posting_times_wat: list[str],
    newsletter_day: str,
    newsletter_time_wat: str,
    newsletter_enabled: bool,
) -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone=WAT)

    # GitHub watcher — every N minutes
    scheduler.add_job(
        github_check_fn,
        trigger="interval",
        minutes=check_interval_minutes,
        id="github_watcher",
        name="GitHub event watcher",
        misfire_grace_time=120,
    )

    # Daily tweets — at each configured WAT time
    for time_str in posting_times_wat:
        hour, minute = map(int, time_str.split(":"))
        # add slight jitter (±5 min) so we don't look like a bot
        jitter = random.randint(-5, 5)
        real_minute = max(0, min(59, minute + jitter))
        scheduler.add_job(
            daily_tweet_fn,
            trigger=CronTrigger(hour=hour, minute=real_minute, timezone=WAT),
            id=f"daily_tweet_{time_str}",
            name=f"Daily tweet at {time_str} WAT",
            misfire_grace_time=300,
        )
        logger.info(f"Scheduled daily tweet at {hour}:{real_minute:02d} WAT (target: {time_str})")

    # Weekly newsletter
    if newsletter_enabled:
        nl_hour, nl_minute = map(int, newsletter_time_wat.split(":"))
        day_map = {
            "monday": "mon", "tuesday": "tue", "wednesday": "wed",
            "thursday": "thu", "friday": "fri", "saturday": "sat", "sunday": "sun"
        }
        day_of_week = day_map.get(newsletter_day.lower(), "sun")
        scheduler.add_job(
            newsletter_fn,
            trigger=CronTrigger(
                day_of_week=day_of_week, hour=nl_hour, minute=nl_minute, timezone=WAT
            ),
            id="weekly_newsletter",
            name="Weekly newsletter draft",
            misfire_grace_time=3600,
        )
        logger.info(f"Scheduled weekly newsletter on {newsletter_day} at {newsletter_time_wat} WAT")

    return scheduler
