"""Recoverable scheduled work derived from persistent database state."""

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from datetime import timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from aiogram import Bot
from redis.asyncio import Redis
from sqlalchemy import select

from app.config import settings
from app.db.base import sessions, utcnow
from app.db.models import AccessLog, Broadcast, Delivery, Submission, Test, User
from app.services import post_service, settings_service, subscription_service
from app.services.broadcast_service import run_batch
from app.services.notification_service import notify_admins
from app.texts import t

logger = logging.getLogger(__name__)


async def bounded_work(
    bot: Bot, redis: Redis, key: str, operation: Callable[[], Awaitable[None]]
) -> bool:
    """Persist three attempts and backoff in Redis; skip exhausted work after restart."""
    async with redis.lock(f"jobs:work:{key}", timeout=43200, blocking_timeout=1):
        state_key = f"jobs:retry:{key}"
        state = await redis.hgetall(state_key)
        attempts = int(state.get(b"attempts", state.get("attempts", 0)))
        next_at = float(state.get(b"next_at", state.get("next_at", 0)))
        if attempts >= 3 or time.time() < next_at:
            return False
        try:
            await operation()
        except Exception:
            attempts += 1
            await redis.hset(
                state_key,
                mapping={"attempts": attempts, "next_at": time.time() + 30 * 2 ** (attempts - 1)},
            )
            logger.warning("Scheduled work failed: %s; attempt=%s", key, attempts)
            if attempts == 3:
                async with sessions() as session:
                    await notify_admins(bot, session, t("scheduler_failed", job=key))
            return False
        await redis.delete(state_key)
        return True


async def heartbeat(bot: Bot, redis: Redis) -> None:
    """Keep the process liveness probe independent of business jobs."""
    Path("storage").mkdir(exist_ok=True)
    Path("storage/heartbeat").touch()


async def tick(bot: Bot, redis: Redis) -> None:
    """Publish due scheduled tests and close expired active tests."""
    async with redis.lock("jobs:tick", timeout=300, blocking_timeout=1):
        async with sessions() as session:
            expired = list(
                (
                    await session.scalars(
                        select(Test.id).where(Test.end_at <= utcnow(), Test.status == "active")
                    )
                ).all()
            )
        async with sessions() as session:
            due = list(
                (
                    await session.scalars(
                        select(Test.id).where(
                            Test.status == "draft",
                            Test.scheduled_at.is_not(None),
                            Test.start_at <= utcnow(),
                        )
                    )
                ).all()
            )
        for test_id in due:

            async def publish_due(test_id: int = test_id) -> None:
                async with sessions.begin() as session:
                    test = await session.scalar(
                        select(Test).where(Test.id == test_id).with_for_update()
                    )
                    if (
                        test
                        and test.status == "draft"
                        and test.scheduled_at
                        and test.start_at <= utcnow()
                    ):
                        await post_service.publish(session, bot, test_id)
                        if test.end_at and test.end_at <= utcnow():
                            await post_service.close(session, bot, test_id)

            await bounded_work(bot, redis, f"publish:{test_id}", publish_due)
        for test_id in expired:

            async def close(test_id: int = test_id) -> None:
                async with sessions.begin() as session:
                    test = await session.scalar(
                        select(Test).where(Test.id == test_id).with_for_update()
                    )
                    if test and test.status == "active" and test.end_at and test.end_at <= utcnow():
                        await post_service.close(session, bot, test_id)

            await bounded_work(bot, redis, f"close:{test_id}", close)


async def broadcasts(bot: Bot, redis: Redis) -> None:
    """Advance broadcasts separately from deadline checks."""
    async with redis.lock("jobs:broadcasts", timeout=43200, blocking_timeout=1):
        async with sessions() as session:
            rows = list(
                (
                    await session.execute(
                        select(Broadcast.id, Broadcast.cursor).where(Broadcast.status == "running")
                    )
                ).all()
            )
        for broadcast_id, cursor in rows:

            async def batch(broadcast_id: int = broadcast_id) -> None:
                await run_batch(bot, broadcast_id)

            await bounded_work(bot, redis, f"broadcast:{broadcast_id}:{cursor}", batch)


async def subscriptions(bot, redis) -> None:
    """Recheck every user daily, invalidating departed invitations."""
    async with redis.lock("jobs:subscriptions", timeout=43200, blocking_timeout=1):
        cursor = 0
        errors = 0
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
                logger.info("Daily subscription check completed; errors=%s", errors)
                return
            for user_id in ids:

                async def recheck(user_id: int = user_id) -> None:
                    async with sessions.begin() as session:
                        user = await session.get(User, user_id)
                        await subscription_service.check(
                            session,
                            bot,
                            redis,
                            user,
                            force=True,
                            request_delay=0.05,
                            fail_on_unknown=True,
                        )

                day = utcnow().astimezone(ZoneInfo(settings.tz)).date().isoformat()
                for attempt in range(3):
                    if await bounded_work(bot, redis, f"subscription:{day}:{user_id}", recheck):
                        break
                    errors += 1
                    failure = await redis.hgetall(f"jobs:retry:subscription:{day}:{user_id}")
                    if int(failure.get(b"attempts", failure.get("attempts", 0))) >= 3:
                        break
                    if attempt < 2:
                        await asyncio.sleep(30 * 2**attempt)
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

                    async def send_reminder(
                        user: User = user, key: str = key, test: Test = test, hours: int = hours
                    ) -> None:
                        await bot.send_message(
                            user.tg_id,
                            t("reminder", user.lang, title=test.title, hours=hours),
                            parse_mode=None,
                        )
                        session.add(Delivery(key=key))
                        await session.flush()

                    await bounded_work(bot, redis, key, send_reminder)
