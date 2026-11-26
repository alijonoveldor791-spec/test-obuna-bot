"""Multi-channel membership checks with short Redis caching."""

import asyncio

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.base import utcnow
from app.db.models import Channel, User
from app.repositories.channels import required
from app.services.referral_service import validate
from app.texts import t


async def check(
    session: AsyncSession, bot: Bot, redis: Redis, user: User, force: bool = False
) -> list[Channel]:
    """Return missing channels; API failures never count as membership."""
    channels = await required(session)
    missing = []
    for channel in channels:
        key = f"sub:{channel.tg_chat_id}:{user.tg_id}"
        cached = None if force else await redis.get(key)
        if cached is not None:
            subscribed = cached in (b"1", "1")
        else:
            try:
                member = await bot.get_chat_member(channel.tg_chat_id, user.tg_id)
                subscribed = member.status in ("member", "administrator", "creator") or (
                    member.status == "restricted" and getattr(member, "is_member", False)
                )
                await redis.set(key, "1" if subscribed else "0", ex=45)
            except (TelegramAPIError, asyncio.TimeoutError):
                subscribed = False
                if await redis.set(f"channel_alert:{channel.id}", "1", ex=300, nx=True):
                    for admin in settings.admins:
                        try:
                            await bot.send_message(admin, t("channel_error"))
                        except TelegramAPIError:
                            pass
        if not subscribed:
            missing.append(channel)
    subscribed = not missing
    if user.is_subscribed and not subscribed:
        user.left_channel_at = utcnow()
    user.is_subscribed = subscribed
    if subscribed:
        user.left_channel_at = None
    newly_valid = await validate(session, user, subscribed)
    if newly_valid and user.referrer_id:
        inviter = await session.get(User, user.referrer_id)
        try:
            await bot.send_message(inviter.tg_id, t("ref_new", inviter.lang))
        except TelegramAPIError:
            pass
    await session.flush()
    return missing
