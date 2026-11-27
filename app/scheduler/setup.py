"""APScheduler tasks restored from DB on every startup."""

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import settings
from app.db.base import utcnow
from app.scheduler.jobs import broadcasts, heartbeat, reminders, subscriptions, tick


def create_scheduler(bot, redis) -> AsyncIOScheduler:
    """Register periodic DB scans rather than volatile one-shot jobs."""
    scheduler = AsyncIOScheduler(timezone=settings.tz)
    for function, trigger, options in (
        (tick, "interval", {"seconds": 30, "next_run_time": utcnow()}),
        (broadcasts, "interval", {"seconds": 1}),
        (heartbeat, "interval", {"seconds": 15}),
        (subscriptions, "cron", {"hour": 3}),
        (reminders, "interval", {"minutes": 5}),
    ):
        scheduler.add_job(
            function,
            trigger,
            args=[bot, redis],
            id=function.__name__,
            replace_existing=True,
            max_instances=1,
            coalesce=True,
            **options,
        )
    return scheduler
