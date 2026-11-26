"""Real PostgreSQL transaction and restart behavior."""

import asyncio
from datetime import timedelta
from types import SimpleNamespace

from redis.asyncio import Redis
from sqlalchemy import func, select

from app.config import settings
from app.db.base import utcnow
from app.db.models import AccessLog, Channel, Delivery, Submission, Test, User
from app.scheduler import jobs
from app.services import grading_service, settings_service
from tests.helpers import bot


async def seed(factory, **overrides):
    async with factory.begin() as session:
        user = User(tg_id=101, full_name="Student")
        channel = Channel(tg_chat_id=-1001, title="Channel", username="channel")
        session.add_all([user, channel])
        await session.flush()
        values = dict(
            code="7234",
            title="Test",
            description="",
            pdf_file_id="pdf",
            pdf_path="none",
            preview_file_id="preview",
            questions_count=2,
            answer_key={"1": "a", "2": "b"},
            status="active",
            start_at=utcnow(),
            created_by=1,
            channel_id=channel.id,
        )
        values.update(overrides)
        test = Test(**values)
        session.add(test)
        await session.flush()
        return user.id, test.id


async def test_parallel_submissions(postgres_factory):
    factory = postgres_factory
    user_id, test_id = await seed(factory)

    async def send():
        try:
            async with factory.begin() as session:
                user = await session.get(User, user_id)
                await grading_service.submit(session, user, "7234 ab")
                return True
        except grading_service.GradingError:
            return False

    accepted = await asyncio.gather(*(send() for _ in range(8)))
    assert sum(accepted) == 1
    async with factory() as session:
        assert await session.scalar(select(func.count()).select_from(Submission)) == 1


async def test_scheduler_restart_and_reminders(postgres_factory, monkeypatch, tmp_path):
    factory = postgres_factory
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(jobs, "sessions", factory)
    monkeypatch.setattr(settings, "admin_ids", "1")
    user_id, test_id = await seed(
        factory,
        end_at=utcnow() + timedelta(minutes=30),
        status="draft",
        scheduled_at=utcnow() - timedelta(seconds=1),
    )
    redis = Redis.from_url(settings.redis_url)
    api = bot()
    try:
        await jobs.tick(api, redis)
        api.send_photo.assert_awaited_once()
        # A second scan acts like a restarted process: persisted state prevents re-publication.
        await jobs.tick(api, redis)
        api.send_photo.assert_awaited_once()
        async with factory.begin() as session:
            session.add(AccessLog(test_id=test_id, user_id=user_id))
            await settings_service.set_value(session, "reminders", True)
        await jobs.reminders(api, redis)
        await jobs.reminders(api, redis)
        async with factory() as session:
            assert await session.scalar(select(func.count()).select_from(Delivery)) == 1
        async with factory.begin() as session:
            test = await session.get(Test, test_id)
            test.end_at = utcnow() - timedelta(seconds=1)
        await jobs.tick(api, redis)
        await jobs.tick(api, redis)
        async with factory() as session:
            assert (await session.get(Test, test_id)).status == "closed"
        assert api.send_message.await_count == 2  # one reminder, one owner notification
    finally:
        await redis.aclose()


async def test_daily_subscription_invalidation(postgres_factory, monkeypatch):
    factory = postgres_factory
    user_id, _ = await seed(factory)
    monkeypatch.setattr(jobs, "sessions", factory)
    redis = Redis.from_url(settings.redis_url)
    api = bot()
    api.get_chat_member.return_value = SimpleNamespace(status="left")
    async with factory.begin() as session:
        user = await session.get(User, user_id)
        user.is_subscribed = True
    try:
        await jobs.subscriptions(api, redis)
        async with factory() as session:
            user = await session.get(User, user_id)
            assert not user.is_subscribed and user.left_channel_at is not None
    finally:
        await redis.aclose()
