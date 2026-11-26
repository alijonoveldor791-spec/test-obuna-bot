"""Persistent, cancellable rate-limited broadcasts."""

import asyncio

from aiogram.exceptions import TelegramAPIError, TelegramForbiddenError, TelegramRetryAfter
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import select

from app.db.base import sessions
from app.db.models import AccessLog, Broadcast, Submission, User
from app.texts import t


def audience_query(broadcast: Broadcast):
    """Build a participant query for the selected audience."""
    query = select(User).where(User.is_blocked.is_(False), User.is_banned.is_(False))
    submitted = select(Submission.user_id).where(Submission.test_id == broadcast.test_id)
    if broadcast.audience == "participants":
        query = query.where(User.id.in_(submitted))
    elif broadcast.audience == "pending":
        downloaded = select(AccessLog.user_id).where(AccessLog.test_id == broadcast.test_id)
        query = query.where(User.id.in_(downloaded), User.id.not_in(submitted))
    elif broadcast.audience == "left":
        query = query.where(User.left_channel_at.is_not(None))
    return query


async def send_one(bot, user: User, broadcast: Broadcast) -> bool:
    """Handle flood wait and blocked recipients without stopping the batch."""
    markup = None
    if broadcast.button_url:
        markup = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=broadcast.button_text, url=broadcast.button_url)]
            ]
        )
    for attempt in range(4):
        try:
            if broadcast.media_file_id:
                await bot.send_photo(
                    user.tg_id,
                    broadcast.media_file_id,
                    caption=broadcast.text,
                    reply_markup=markup,
                    parse_mode=None,
                )
            else:
                await bot.send_message(
                    user.tg_id, broadcast.text, reply_markup=markup, parse_mode=None
                )
            return True
        except TelegramForbiddenError:
            user.is_blocked = True
            return False
        except TelegramRetryAfter as exc:
            await asyncio.sleep(exc.retry_after)
        except TelegramAPIError:
            return False
    return False


async def run_batch(bot, broadcast_id: int, batch_size: int = 20) -> None:
    """Send a small durable batch; jobs resume from the saved cursor."""
    async with sessions.begin() as session:
        broadcast = await session.scalar(
            select(Broadcast).where(Broadcast.id == broadcast_id).with_for_update()
        )
        if broadcast is None or broadcast.status != "running":
            return
        users = list(
            (
                await session.scalars(
                    audience_query(broadcast)
                    .where(User.id > broadcast.cursor)
                    .order_by(User.id)
                    .limit(batch_size)
                )
            ).all()
        )
        for user in users:
            sent = await send_one(bot, user, broadcast)
            broadcast.sent += int(sent)
            broadcast.failed += int(not sent)
            broadcast.cursor = user.id
            await asyncio.sleep(0.05)
        if not users or len(users) < batch_size:
            broadcast.status = "done"
        await session.flush()
    if broadcast.status == "done":
        from app.config import settings

        for admin in settings.admins:
            try:
                await bot.send_message(
                    admin,
                    t(
                        "broadcast_progress",
                        id=broadcast.id,
                        status=broadcast.status,
                        total=broadcast.total,
                        sent=broadcast.sent,
                        failed=broadcast.failed,
                    ),
                )
            except TelegramAPIError:
                pass
