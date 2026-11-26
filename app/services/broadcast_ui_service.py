"""Preview-and-confirm broadcast composer."""

from sqlalchemy import func, select

from app.db.models import Broadcast, Test
from app.keyboards.admin import buttons
from app.services.admin_service import require
from app.services.broadcast_service import audience_query
from app.services.errors import BusinessError
from app.states.broadcast import BroadcastInput
from app.texts import t


async def audience(message, state, session, user) -> None:
    """Validate a broadcast audience."""
    await require(session, user.tg_id, "broadcast")
    parts = (message.text or "").split()
    if not parts or parts[0] not in ("all", "participants", "pending", "left"):
        raise BusinessError(t("invalid"))
    test_id = int(parts[1]) if parts[0] in ("participants", "pending") else None
    if test_id and await session.get(Test, test_id) is None:
        raise BusinessError(t("no_test"))
    await state.update_data(broadcast={"audience": parts[0], "test_id": test_id})
    await state.set_state(BroadcastInput.content)
    await message.answer(t("broadcast_text"))


async def content(message, state, session, user) -> None:
    """Accept text or one photo with caption."""
    await require(session, user.tg_id, "broadcast")
    data = await state.get_data()
    draft = data["broadcast"]
    text = message.caption if message.photo else message.text
    if not text or len(text) > (1024 if message.photo else 4000):
        raise BusinessError(t("invalid"))
    draft.update(text=text, media_file_id=message.photo[-1].file_id if message.photo else None)
    await state.update_data(broadcast=draft)
    await state.set_state(BroadcastInput.button)
    await message.answer(t("broadcast_button"))


async def button(message, state, session, user) -> None:
    """Save a draft after rendering the actual outgoing message."""
    from urllib.parse import urlparse

    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    await require(session, user.tg_id, "broadcast")
    data = await state.get_data()
    draft = data["broadcast"]
    if message.text != "-":
        label, url = message.text.split("|", maxsplit=1)
        label, url = label.strip(), url.strip()
        if not 1 <= len(label) <= 64 or urlparse(url).scheme != "https" or not urlparse(url).netloc:
            raise BusinessError(t("invalid"))
        draft.update(button_text=label, button_url=url)
    row = Broadcast(**draft)
    session.add(row)
    await session.flush()
    row.total = await session.scalar(
        select(func.count()).select_from(audience_query(row).subquery())
    )
    markup = (
        InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text=row.button_text, url=row.button_url)]]
        )
        if row.button_url
        else None
    )
    if row.media_file_id:
        await message.answer_photo(
            row.media_file_id, caption=row.text, reply_markup=markup, parse_mode=None
        )
    else:
        await message.answer(row.text, reply_markup=markup, parse_mode=None)
    await message.answer(
        t("confirm"),
        reply_markup=buttons(
            [("broadcast_send", f"bc:send:{row.id}"), ("cancel", f"bc:cancel:{row.id}")]
        ),
    )
    await state.set_state(BroadcastInput.confirm)
    await state.update_data(broadcast_id=row.id)


async def action(callback, state, session, user, action: str, broadcast_id: int) -> None:
    """Start or cancel a persisted broadcast; report current progress."""
    await require(session, user.tg_id, "broadcast")
    row = await session.scalar(
        select(Broadcast).where(Broadcast.id == broadcast_id).with_for_update()
    )
    if row is None:
        raise BusinessError(t("empty"))
    if action == "send" and row.status == "draft":
        row.status = "running"
    elif action == "cancel" and row.status in ("draft", "running"):
        row.status = "cancelled"
    await state.clear()
    await callback.message.answer(
        t(
            "broadcast_progress",
            id=row.id,
            status=row.status,
            total=row.total,
            sent=row.sent,
            failed=row.failed,
        ),
        reply_markup=buttons(
            [("broadcast_stop", f"bc:cancel:{row.id}"), ("check", f"bc:status:{row.id}")]
        ),
    )
