"""Recoverable scheduled work derived from persistent database state."""

import logging
from datetime import timedelta

from aiogram.exceptions import TelegramAPIError
from sqlalchemy import select

from app.db.base import sessions, utcnow
from app.db.models import AccessLog, Broadcast, Delivery, Submission, Test, User
from app.services import post_service, settings_service, subscription_service
from app.services.broadcast_service import run_batch

logger = logging.getLogger(__name__)


async def tick(bot, redis) -> None:
    """Publish due drafts, close deadlines and advance broadcasts."""
    from pathlib import Path

    Path("storage").mkdir(exist_ok=True)
    Path("storage/heartbeat").touch()
    async with redis.lock("jobs:tick", timeout=300, blocking_timeout=1):
        async with sessions() as session:
            now = utcnow()
            due = list(
                (
                    await session.scalars(
                        select(Test.id).where(Test.scheduled_at <= now, Test.status != "closed")
                    )
                ).all()
            )
            expired = list(
                (
                    await session.scalars(
                        select(Test.id).where(
                            Test.end_at <= now, Test.status.in_(["active", "paused"])
                        )
                    )
                ).all()
            )
            broadcasts = list(
                (
                    await session.scalars(select(Broadcast.id).where(Broadcast.status == "running"))
                ).all()
            )
        for test_id in due:
            try:
                async with sessions.begin() as session:
                    test = await session.scalar(
                        select(Test).where(Test.id == test_id).with_for_update()
                    )
                    if test.scheduled_at is not None and test.scheduled_at <= utcnow():
                        if test.end_at and test.end_at <= utcnow():
                            await post_service.close(session, bot, test_id)
                        else:
                            await post_service.publish(session, bot, test_id)
            except Exception:
                logger.exception("Scheduled publication failed for %s", test_id)
        for test_id in expired:
            try:
                async with sessions.begin() as session:
                    await post_service.close(session, bot, test_id)
            except Exception:
                logger.exception("Automatic closure failed for %s", test_id)
        for broadcast_id in broadcasts:
            try:
                await run_batch(bot, broadcast_id)
            except Exception:
                logger.exception("Broadcast failed for %s", broadcast_id)


async def subscriptions(bot, redis) -> None:
    """Recheck every user daily, invalidating departed invitations."""
    async with redis.lock("jobs:subscriptions", timeout=43200, blocking_timeout=1):
        cursor = 0
        while True:
            async with sessions() as session:
                ids = list(
                    (
                        await session.scalars(
                            select(User.id).where(User.id > cursor).order_by(User.id).limit(100)
                        )
                    ).all()
                )
            if not ids:
                return
            for user_id in ids:
                async with sessions.begin() as session:
                    user = await session.get(User, user_id)
                    await subscription_service.check(session, bot, redis, user, force=True)
                cursor = user_id


async def reminders(bot, redis) -> None:
    """Send deduplicated reminders for 24-hour and 1-hour windows."""
    async with redis.lock("jobs:reminders", timeout=600, blocking_timeout=1):
        async with sessions.begin() as session:
            if not await settings_service.get(session, "reminders"):
                return
            now = utcnow()
            tests = list(
                (
                    await session.scalars(
                        select(Test).where(
                            Test.status == "active",
                            Test.end_at > now,
                            Test.end_at <= now + timedelta(hours=24),
                        )
                    )
                ).all()
            )
            for test in tests:
                hours = 1 if test.end_at <= now + timedelta(hours=1) else 24
                submitted = select(Submission.user_id).where(Submission.test_id == test.id)
                users = (
                    await session.scalars(
                        select(User)
                        .join(AccessLog, AccessLog.user_id == User.id)
                        .where(
                            AccessLog.test_id == test.id,
                            User.id.not_in(submitted),
                            User.is_banned.is_(False),
                            User.is_blocked.is_(False),
                        )
                    )
                ).all()
                for user in users:
                    key = f"reminder:{test.id}:{user.id}:{hours}"
                    if await session.scalar(select(Delivery.id).where(Delivery.key == key)):
                        continue
                    from app.texts import t

                    try:
                        await bot.send_message(
                            user.tg_id,
                            t("reminder", user.lang, title=test.title, hours=hours),
                            parse_mode=None,
                        )
                        session.add(Delivery(key=key))
                        await session.flush()
                    except TelegramAPIError:
                        pass
