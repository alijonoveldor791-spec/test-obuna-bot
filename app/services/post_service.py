"""Test publication and result announcement."""

from zoneinfo import ZoneInfo

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import BufferedInputFile, InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.base import utcnow
from app.db.models import Channel, Test, User
from app.services.errors import BusinessError
from app.services.pdf_service import preview
from app.services.ranking_service import recalculate
from app.texts import t
from app.utils.deeplink import link


def caption(test: Test, channel: Channel | None) -> str:
    """Keep required metadata inside Telegram's UTF-16 caption limit."""
    deadline = (
        test.end_at.astimezone(ZoneInfo("Asia/Tashkent")).strftime("%Y-%m-%d %H:%M")
        if test.end_at
        else t("unlimited")
    )
    channel_url = (
        (f"https://t.me/{channel.username}" if channel.username else channel.invite_link or "")
        if channel
        else ""
    )
    values = dict(
        title=test.title[:200],
        description="",
        code=test.code,
        deadline=deadline,
        prizes=test.prizes_count,
        channel=channel_url,
        bot=f"https://t.me/{settings.bot_username}",
    )
    fixed = t("caption", **values)
    budget = max(0, 1024 - len(fixed.encode("utf-16-le")) // 2)
    description = test.description
    while len(description.encode("utf-16-le")) // 2 > budget:
        description = description[:-1]
    values["description"] = description
    return t("caption", **values)


async def publish(
    session: AsyncSession, bot: Bot, test_id: int, destination: int | None = None
) -> None:
    """Publish while holding the lifecycle lock; update only after API success."""
    test = await session.scalar(select(Test).where(Test.id == test_id).with_for_update())
    if test is None or test.status == "closed":
        raise BusinessError(t("no_test"))
    channel = await session.get(Channel, test.channel_id) if test.channel_id else None
    if destination is None and channel is None:
        raise BusinessError(t("channel_error"))
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=t("test_button"), url=link(settings.bot_username, f"test_{test.id}")
                )
            ]
        ]
    )
    photo = test.preview_file_id or BufferedInputFile(
        await preview(test.pdf_path), filename="preview.jpg"
    )
    message = await bot.send_photo(
        destination or channel.tg_chat_id,
        photo,
        caption=caption(test, channel),
        reply_markup=keyboard,
        parse_mode=None,
    )
    test.preview_file_id = message.photo[-1].file_id
    test.status, test.start_at, test.scheduled_at = "active", utcnow(), None
    if destination is None:
        test.channel_post_id = message.message_id
    await session.flush()


async def close(session: AsyncSession, bot: Bot, test_id: int) -> None:
    """Close once and notify owners to review winners."""
    test = await session.scalar(select(Test).where(Test.id == test_id).with_for_update())
    if test.status == "closed":
        return
    test.status, test.scheduled_at = "closed", None
    await recalculate(session, test.id)
    for admin in settings.admins:
        try:
            await bot.send_message(admin, t("closed_notice", title=test.title), parse_mode=None)
        except TelegramAPIError:
            pass
    await session.flush()


async def results(session: AsyncSession, bot: Bot, test_id: int) -> None:
    """Announce reviewed winners once after admin confirmation."""
    test = await session.scalar(select(Test).where(Test.id == test_id).with_for_update())
    if test.status != "closed" or test.results_published:
        raise BusinessError(t("invalid"))
    channel = await session.get(Channel, test.channel_id)
    if channel is None:
        raise BusinessError(t("channel_error"))
    ranked = await recalculate(session, test.id)
    users = {
        r.user_id: await session.get(User, r.user_id) for r in ranked[: max(10, test.prizes_count)]
    }
    body = t(
        "winner_post",
        title=test.title,
        ranking="\n".join(
            t("rank_row", rank=r.rank, name=users[r.user_id].full_name, percent=r.score_percent)
            for r in ranked[:10]
        ),
        winners=", ".join(users[r.user_id].full_name for r in ranked[: test.prizes_count]) or "?",
    )
    if test.show_key_after_close:
        body += "\n" + t("answer_key", key=", ".join(k + v for k, v in test.answer_key.items()))
    # Telegram text limit: long keys are sent separately.
    for offset in range(0, len(body), 3500):
        await bot.send_message(channel.tg_chat_id, body[offset : offset + 3500], parse_mode=None)
    test.results_published = True
    for row in ranked[: test.prizes_count]:
        try:
            await bot.send_message(
                users[row.user_id].tg_id,
                t("winner_dm", title=test.title, rank=row.rank),
                parse_mode=None,
            )
        except TelegramAPIError:
            pass
    await session.flush()
