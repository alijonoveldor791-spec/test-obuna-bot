"""R1 service and middleware regressions."""

from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from aiogram.exceptions import TelegramBadRequest
from aiogram.methods import GetChatMember
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import settings
from app.db.base import Base
from app.db.models import Admin, Referral, User
from app.middlewares.antiflood import AntifloodMiddleware
from app.middlewares.db_session import DatabaseMiddleware
from app.repositories.users import upsert
from app.scheduler import jobs
from app.scheduler.setup import create_scheduler
from app.services.admin_service import channel_command
from app.services.errors import BusinessError
from app.services.notification_service import notify_admins
from app.services.referral_service import count
from app.services.subscription_service import check
from app.services.test_time_service import explicit
from tests.helpers import callback, message
from tests.test_scheduler import MemoryRedis


async def test_test_specific_referrals(db, domain):
    d = domain
    d.user.is_subscribed = True
    referral = Referral(
        inviter_id=d.owner.id,
        invited_id=d.user.id,
        is_valid=True,
        created_at=d.test.start_at - timedelta(seconds=1),
    )
    db.add(referral)
    await db.flush()
    assert await count(db, d.owner.id, d.test) == 0
    referral.created_at = d.test.start_at + timedelta(seconds=1)
    await db.flush()
    assert await count(db, d.owner.id, d.test) == 1
    d.user.is_subscribed = False
    await db.flush()
    assert await count(db, d.owner.id, d.test) == 0


async def test_unknown_membership_preserves_state(db, domain):
    d = domain
    d.user.is_subscribed = True
    row = Referral(inviter_id=d.owner.id, invited_id=d.user.id, is_valid=True)
    db.add(row)
    await db.flush()
    d.bot.get_chat_member.side_effect = TelegramBadRequest(
        method=GetChatMember(chat_id=1, user_id=2), message="Unavailable"
    )
    assert await check(db, d.bot, d.redis, d.user, force=True)
    assert d.user.is_subscribed and row.is_valid and d.user.left_channel_at is None


async def test_upsert_unblocks(db, domain):
    domain.owner.is_blocked = True
    await upsert(db, domain.message.from_user)
    assert not domain.owner.is_blocked


async def test_readding_main_channel(db, domain):
    d = domain
    d.bot.get_chat = AsyncMock(
        return_value=SimpleNamespace(
            id=d.channel.tg_chat_id,
            title="Channel",
            username="channel",
            invite_link=None,
            type="channel",
        )
    )
    d.bot.get_me = AsyncMock(return_value=SimpleNamespace(id=42))
    d.bot.get_chat_member.return_value = SimpleNamespace(
        status="administrator", can_post_messages=True
    )
    await channel_command(db, d.bot, str(d.channel.tg_chat_id))
    assert d.channel.is_main


async def test_callback_and_group_boundary():
    redis = SimpleNamespace(eval=AsyncMock(return_value=4))
    handler = AsyncMock()
    event = callback("x")
    await AntifloodMiddleware(redis)(handler, event, {})
    event.answer.assert_awaited_once()
    event.message.chat.type = "group"
    redis.eval.reset_mock()
    await AntifloodMiddleware(redis)(handler, event, {})
    await DatabaseMiddleware(redis)(handler, event, {})
    redis.eval.assert_not_awaited()
    handler.assert_not_awaited()


async def test_notification_recipients(db, domain):
    db.add_all([Admin(tg_id=91, role="admin"), Admin(tg_id=92, role="moderator")])
    await db.flush()
    await notify_admins(domain.bot, db, "test")
    assert {call.args[0] for call in domain.bot.send_message.await_args_list} == {1, 91}


async def test_timezone(monkeypatch):

    monkeypatch.setattr(settings, "tz", "UTC")
    assert str(create_scheduler(None, None).timezone) == "UTC"
    assert str(explicit("2099-01-01 12:00").tzinfo) == "UTC"


async def test_bootstrap_commits_on_business_error(tmp_path, monkeypatch):

    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'bootstrap.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory.begin() as session:
        session.add(User(tg_id=1, full_name="Inviter"))
    monkeypatch.setattr("app.middlewares.db_session.sessions", factory)
    lock = SimpleNamespace(acquire=AsyncMock(return_value=True), release=AsyncMock())
    redis = SimpleNamespace(lock=lambda *args, **kwargs: lock)

    async def fail(event, data):
        raise BusinessError("invalid")

    with pytest.raises(BusinessError):
        await DatabaseMiddleware(redis)(fail, message("/start ref_1", tg_id=2), {})
    async with factory() as session:
        user = await session.scalar(select(User).where(User.tg_id == 2))
        assert user and user.referrer_id
        assert await session.scalar(select(Referral.id).where(Referral.invited_id == user.id))
    await engine.dispose()


async def test_daily_job_continues_and_throttles(db, domain, monkeypatch, caplog):

    class Context:
        async def __aenter__(self):
            return db

        async def __aexit__(self, *args):
            return False

    class Factory:
        def __call__(self):
            return Context()

        def begin(self):
            return Context()

    monkeypatch.setattr(jobs, "sessions", Factory())
    checker = AsyncMock(side_effect=[RuntimeError("unknown"), [], []])
    monkeypatch.setattr(jobs.subscription_service, "check", checker)
    clock = [1000.0]
    monkeypatch.setattr(jobs.time, "time", lambda: clock[0])

    async def advance(seconds):
        clock[0] += seconds

    monkeypatch.setattr(jobs.asyncio, "sleep", advance)
    with caplog.at_level("INFO"):
        await jobs.subscriptions(domain.bot, MemoryRedis())
    assert checker.await_count == 3
    assert all(c.kwargs["request_delay"] >= 0.05 for c in checker.await_args_list)
    assert "errors=1" in caplog.text


async def test_membership_api_request_is_throttled(db, domain, monkeypatch):
    sleep = AsyncMock()
    monkeypatch.setattr("app.services.subscription_service.asyncio.sleep", sleep)
    await check(db, domain.bot, domain.redis, domain.user, force=True, request_delay=0.05)
    sleep.assert_awaited_once_with(0.05)
