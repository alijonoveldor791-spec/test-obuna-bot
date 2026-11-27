"""Test publication and result announcement."""

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.base import utcnow
from app.db.models import Channel, Test, User
from app.services.errors import BusinessError
from app.services.notification_service import notify_admins
from app.services.ranking_service import recalculate
from app.services.test_time_service import aware, display
from app.texts import t
from app.utils.deeplink import link


def caption(test: Test, channel: Channel | None) -> str:
    """Keep required metadata inside Telegram's UTF-16 caption limit."""
    if test.custom_caption is not None:
        return test.custom_caption
    start = display(test.start_at or utcnow())
    window = (
        t("time_window", start=start, end=display(test.end_at))
        if test.end_at
        else t("time_open", start=start)
    )
    channel_url = (
        (f"https://t.me/{channel.username}" if channel.username else channel.invite_link or "")
        if channel
        else ""
    )
    return t(
        "caption",
        title=test.title[:200],
        code=test.code,
        deadline=window,
        channel=channel_url,
        bot=f"https://t.me/{settings.bot_username}",
    )


async def publish(
    session: AsyncSession, bot: Bot, test_id: int, destination: int | None = None
) -> None:
    """Publish while holding the lifecycle lock; update only after API success."""
    test = await session.scalar(select(Test).where(Test.id == test_id).with_for_update())
    if test is None or test.status == "closed":
        raise BusinessError(t("no_test"))
    if test.start_at and aware(test.start_at) > utcnow():
        raise BusinessError(t("not_started", start=display(test.start_at)))
    if test.status == "active" and test.channel_post_id and destination is None:
        raise BusinessError(t("test_changed"))
    channel = await session.get(Channel, test.channel_id) if test.channel_id else None
    if destination is None and channel is None:
        raise BusinessError(t("channel_error"))
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t("test_button"), url=link(settings.bot_username, "test"))]
        ]
    )
    if not test.preview_file_id:
        raise BusinessError(t("preview_missing"))
    photo = test.preview_file_id
    message = await bot.send_photo(
        destination or channel.tg_chat_id,
        photo,
        caption=caption(test, channel),
        reply_markup=keyboard,
        parse_mode=None,
    )
    test.preview_file_id = message.photo[-1].file_id
    test.status, test.start_at, test.scheduled_at = "active", test.start_at or utcnow(), None
    test.max_attempts = 1
    if destination is None:
        test.channel_post_id = message.message_id
    await session.flush()


async def close(session: AsyncSession, bot: Bot, test_id: int) -> None:
    """Close once and notify administrators to review results."""
    test = await session.scalar(select(Test).where(Test.id == test_id).with_for_update())
    if test.status == "closed":
        return
    if test.end_at is None or aware(test.end_at) > utcnow():
        test.end_at = utcnow()
    test.status, test.scheduled_at = "closed", None
    await recalculate(session, test.id)
    await notify_admins(bot, session, t("closed_notice", title=test.title))
    await session.flush()


async def results(session: AsyncSession, bot: Bot, test_id: int) -> None:
    """Publish the closed test top ten once, without private announcements."""
    test = await session.scalar(select(Test).where(Test.id == test_id).with_for_update())
    if test is None or test.status != "closed" or test.results_published:
        raise BusinessError(t("invalid"))
    channel = await session.get(Channel, test.channel_id)
    if channel is None:
        raise BusinessError(t("channel_error"))
    ranked = await recalculate(session, test.id)
    lines = []
    for row in ranked[:10]:
        person = await session.get(User, row.user_id)
        lines.append(
            t(
                "top_row",
                rank=row.rank,
                name=person.full_name[:80],
                correct=row.correct_count,
                percent=row.score_percent,
            )
        )
    body = t("results_post", title=test.title, ranking="\n".join(lines) or t("empty"))
    await bot.send_message(channel.tg_chat_id, body, parse_mode=None)
    test.results_published = True
    await session.flush()
