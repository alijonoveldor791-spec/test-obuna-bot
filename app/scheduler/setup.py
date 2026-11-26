"""APScheduler tasks restored from DB on every startup."""

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.scheduler.jobs import reminders, subscriptions, tick


def create_scheduler(bot, redis) -> AsyncIOScheduler:
    """Register periodic DB scans rather than volatile one-shot jobs."""
    scheduler = AsyncIOScheduler(timezone="Asia/Tashkent")
    for function, trigger, options in (
        (tick, "interval", {"seconds": 1}),
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
