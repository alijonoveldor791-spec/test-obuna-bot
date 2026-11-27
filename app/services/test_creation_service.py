"""Five-step test creation with reply-only controls."""

import re
import secrets
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from aiogram import Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, KeyboardButton
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import MAX_PDF_BYTES
from app.db.models import Channel, Test
from app.keyboards.reply import build, input_menu
from app.services.answer_parser import parse_key
from app.services.errors import BusinessError
from app.services.pdf_service import preview
from app.services.post_service import caption
from app.services.settings_service import get
from app.services.test_time_service import beginning, ending
from app.states.add_test import AddTest
from app.texts import t
from app.utils.files import pdf_destination

FIELDS = ("answer_key", "start_at", "end_at", "referral_count", "channel_id")
SHORTCUTS = {
    "start_at": ["start_now", "start_tomorrow"],
    "end_at": ["day1", "day3", "day7", "unlimited_btn"],
    "referral_count": ["no_referral", "ref3", "ref5", "ref10"],
}


def preview_keys(data: dict) -> list[str]:
    """Expose publication choices appropriate to the selected beginning."""
    return (["publish", "send_me"] if data["draft"].get("start_now") else ["schedule"]) + [
        "edit_post",
        "cancel_input",
    ]


async def start(message: Any, state: FSMContext) -> None:
    """Start a new PDF conversation."""
    await state.clear()
    await state.update_data(nav_menu="tests")
    await state.set_state(AddTest.pdf)
    await message.answer(
        t("step_prompt", step=1, prompt=t("prompt_pdf")), reply_markup=input_menu()
    )


async def receive_pdf(message: Any, state: FSMContext, session: AsyncSession, bot: Bot) -> None:
    """Validate and download a Telegram PDF before collecting metadata."""
    doc = message.document
    if doc is None or doc.mime_type != "application/pdf":
        raise BusinessError(t("pdf_invalid"))
    if not doc.file_size or doc.file_size > MAX_PDF_BYTES:
        raise BusinessError(t("pdf_limit"))
    code = await available_code(session)
    filename = (
        re.sub(r"(?i)\.pdf$", "", getattr(doc, "file_name", None) or "")
        .replace("_", " ")
        .replace("-", " ")
        .strip()
    )
    title = (message.caption or "").strip() or filename or t("default_test_title")
    path = pdf_destination()
    try:
        await bot.download(doc, destination=path)
        if path.stat().st_size > MAX_PDF_BYTES:
            raise BusinessError(t("pdf_limit"))
        await preview(path)
    except Exception:
        path.unlink(missing_ok=True)
        raise
    await discard(state)
    await state.update_data(
        draft={
            "pdf_file_id": doc.file_id,
            "pdf_path": str(path),
            "title": title[:200],
            "code": code,
        },
        field_index=0,
    )
    await state.set_state(AddTest.fields)
    await prompt(message, state, session)


async def prompt(message: Any, state: FSMContext, session: AsyncSession) -> None:
    """Render the current numbered step, skipping a unique channel selection."""
    data = await state.get_data()
    index = data["field_index"]
    if index >= len(FIELDS):
        await show_preview(message, state, session)
        return
    field = FIELDS[index]
    if field == "channel_id":
        channels = list((await session.scalars(select(Channel).order_by(Channel.id))).all())
        if not channels:
            raise BusinessError(t("no_channels"))
        if len(channels) == 1:
            draft = data["draft"]
            draft["channel_id"] = channels[0].id
            await state.update_data(draft=draft, field_index=len(FIELDS), auto_channel=True)
            await show_preview(message, state, session)
            return
        choices = {t("channel_choice", title=c.title, id=c.id): c.id for c in channels}
        await state.update_data(channel_choices=choices, auto_channel=False)
        keyboard = input_menu()
        keyboard.keyboard[0:0] = [[KeyboardButton(text=label)] for label in choices]
    else:
        keyboard = build(SHORTCUTS.get(field, []) + ["back", "cancel_input"])
    await message.answer(
        t("prompt_channel_id")
        if field == "channel_id"
        else t(
            "step_prompt",
            step=index + 2,
            prompt=t("prompt_" + field),
        ),
        reply_markup=keyboard,
    )


async def field_value(message: Any, state: FSMContext, session: AsyncSession) -> None:
    """Validate one field, normalize it, then advance to the next question."""
    data = await state.get_data()
    draft = data["draft"]
    field = FIELDS[data["field_index"]]
    value = (message.text or "").strip()
    if field == "answer_key":
        value = parse_key(value).answers
        draft["questions_count"] = len(value)
    elif field == "start_at":
        parsed, immediate = beginning(value)
        draft["start_now"] = immediate
        value = parsed.isoformat()
    elif field == "end_at":
        parsed = ending(value, datetime.fromisoformat(draft["start_at"]))
        value = parsed.isoformat() if parsed else None
    elif field == "referral_count":
        choices = {t("no_referral"): 0, t("ref3"): 3, t("ref5"): 5, t("ref10"): 10}
        if value not in choices:
            raise BusinessError(t("select_from_list"))
        value = choices[value]
    else:
        choices = data.get("channel_choices", {})
        if value not in choices:
            raise BusinessError(t("select_from_list"))
        value = choices[value]
        if await session.get(Channel, value) is None:
            raise BusinessError(t("channel_error"))
    draft[field] = value
    # A stale Telegram preview must not survive a replaced PDF; captions are rebuilt below.
    await state.update_data(draft=draft, field_index=data["field_index"] + 1)
    await prompt(message, state, session)


async def show_preview(message: Any, state: FSMContext, session: AsyncSession) -> None:
    """Cache the Telegram photo and offer reply publication/draft actions."""
    data = await state.get_data()
    draft = data["draft"]
    channel = await session.get(Channel, draft["channel_id"])
    if channel is None:
        raise BusinessError(t("channel_error"))
    values = {key: value for key, value in draft.items() if key != "start_now"}
    for key in ("start_at", "end_at"):
        values[key] = datetime.fromisoformat(draft[key]) if draft.get(key) else None
    values.update(max_attempts=1, referral_required=draft["referral_count"] > 0)
    photo = draft.get("preview_file_id") or BufferedInputFile(
        await preview(draft["pdf_path"]), filename="preview.jpg"
    )
    sent = await message.answer_photo(
        photo,
        caption=caption(Test(**values, created_by=message.from_user.id), channel),
        reply_markup=build(preview_keys(data)),
        parse_mode=None,
    )
    draft["preview_file_id"] = sent.photo[-1].file_id
    draft["max_attempts"] = 1
    await state.update_data(draft=draft)
    await state.set_state(AddTest.confirm)
    await message.answer(
        t("preview_summary", questions=draft["questions_count"], referral=draft["referral_count"])
    )


async def confirm(
    message: Any, state: FSMContext, session: AsyncSession, clear: bool = True
) -> int:
    """Persist a new test window; retain preview state while publication is pending."""
    data = await state.get_data()
    if await state.get_state() != AddTest.confirm.state or not data.get("draft"):
        raise BusinessError(t("invalid"))
    draft = {key: value for key, value in data["draft"].items() if key != "start_now"}
    draft.update(
        start_at=datetime.fromisoformat(draft["start_at"]).astimezone(UTC),
        scheduled_at=None
        if data["draft"].get("start_now")
        else datetime.fromisoformat(draft["start_at"]).astimezone(UTC),
        end_at=datetime.fromisoformat(draft["end_at"]).astimezone(UTC)
        if draft.get("end_at")
        else None,
        referral_required=draft["referral_count"] > 0,
        max_attempts=1,
        show_key_after_close=await get(session, "show_key_after_close"),
    )
    try:
        async with session.begin_nested():
            row = Test(**draft, created_by=message.from_user.id, status="draft")
            session.add(row)
            await session.flush()
    except IntegrityError as exc:
        raise BusinessError(t("duplicate_code")) from exc
    if clear:
        await state.clear()
    return row.id


async def back(message: Any, state: FSMContext, session: AsyncSession) -> None:
    """Return one question, accounting for an automatically chosen channel."""
    data = await state.get_data()
    current = await state.get_state()
    if current == AddTest.confirm.state:
        index = len(FIELDS) - (2 if data.get("auto_channel") else 1)
    else:
        index = data.get("field_index", 0) - 1
    if index < 0:
        await state.set_state(AddTest.pdf)
        await message.answer(
            t("step_prompt", step=1, prompt=t("prompt_pdf")), reply_markup=input_menu()
        )
        return
    await state.update_data(field_index=index)
    await state.set_state(AddTest.fields)
    await prompt(message, state, session)


async def discard(state: FSMContext) -> None:
    """Remove only unpersisted PDFs owned by this creation flow."""
    data = await state.get_data()
    path = Path(data.get("draft", {}).get("pdf_path", ""))
    root = Path("storage/pdf").resolve()
    if path.is_file() and path.resolve().is_relative_to(root):
        path.unlink(missing_ok=True)


async def available_code(session: AsyncSession) -> str:
    """Generate an unused four-digit code; the unique index handles races."""
    used = set(
        (await session.scalars(select(Test.code).where(Test.status.in_(("draft", "active"))))).all()
    )
    available = [str(n) for n in range(1000, 10000) if str(n) not in used]
    if not available:
        raise BusinessError(t("codes_full"))
    return secrets.choice(available)
