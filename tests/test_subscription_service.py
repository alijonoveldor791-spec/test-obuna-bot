"""Membership cache and forced refresh behavior."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

from aiogram.exceptions import TelegramBadRequest
from aiogram.methods import GetChatMember

from app.db.models import Channel, User
from app.services.subscription_service import check


async def test_cache_and_refresh(db):
    user = User(tg_id=4, full_name="Ali")
    db.add_all([user, Channel(tg_chat_id=-1001, title="Channel", username="channel")])
    await db.flush()
    redis = SimpleNamespace(get=AsyncMock(return_value=None), set=AsyncMock())
    bot = SimpleNamespace(
        get_chat_member=AsyncMock(return_value=SimpleNamespace(status="member")),
        send_message=AsyncMock(),
    )
    assert await check(db, bot, redis, user) == []
    assert user.is_subscribed
    redis.get.return_value = b"1"
    bot.get_chat_member.reset_mock()
    assert await check(db, bot, redis, user) == []
    bot.get_chat_member.assert_not_awaited()
    bot.get_chat_member.return_value = SimpleNamespace(status="left")
    assert len(await check(db, bot, redis, user, force=True)) == 1
    assert user.left_channel_at is not None


async def test_multiple_and_error(db):

    user = User(tg_id=4, full_name="Ali")
    db.add_all(
        [user, Channel(tg_chat_id=-1001, title="One"), Channel(tg_chat_id=-1002, title="Two")]
    )
    await db.flush()
    redis = SimpleNamespace(get=AsyncMock(return_value=None), set=AsyncMock(return_value=True))
    bot = SimpleNamespace(
        get_chat_member=AsyncMock(
            side_effect=TelegramBadRequest(
                method=GetChatMember(chat_id=1, user_id=4), message="bad"
            )
        ),
        send_message=AsyncMock(),
    )
    assert len(await check(db, bot, redis, user)) == 2
    assert not user.is_subscribed
