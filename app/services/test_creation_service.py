"""Validated multi-step draft creation."""

import re
import secrets
from datetime import datetime
from zoneinfo import ZoneInfo

from aiogram.types import BufferedInputFile
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import MAX_PDF_BYTES
from app.db.base import utcnow
from app.db.models import Channel, Test
from app.keyboards.admin import buttons
from app.keyboards.reply import input_menu
from app.services.answer_parser import parse_key
from app.services.errors import BusinessError
from app.services.pdf_service import preview
from app.services.post_service import caption
from app.services.settings_service import get
from app.states.add_test import AddTest
from app.texts import t
from app.utils.files import pdf_destination

FIELDS = (
    "title",
    "code",
    "description",
    "questions_count",
    "answer_key",
    "end_at",
    "prizes_count",
    "referral_enabled",
    "referral_count",
    "max_attempts",
    "channel_id",
)


def parse_date(value: str, future: bool = True) -> datetime | None:
    """Parse a Tashkent local deadline or unlimited value."""
    if value.lower() in ("cheksiz", "-"):
        return None
    result = datetime.strptime(value, "%Y-%m-%d %H:%M").replace(tzinfo=ZoneInfo("Asia/Tashkent"))
    if future and result <= utcnow():
        raise BusinessError(t("invalid"))
    return result


async def start(message, state) -> None:
    """Begin PDF intake."""
    await state.clear()
    await state.set_state(AddTest.pdf)
    await message.answer(t("prompt_pdf"), reply_markup=input_menu())


async def receive_pdf(message, state, session: AsyncSession, bot) -> None:
    """Download and validate the PDF before accepting metadata."""
    doc = message.document
    if doc is None or doc.mime_type != "application/pdf":
        raise BusinessError(t("pdf_invalid"))
    if not doc.file_size or doc.file_size > MAX_PDF_BYTES:
        raise BusinessError(t("pdf_limit"))
    path = pdf_destination()
    await bot.download(doc, destination=path)
    if path.stat().st_size > MAX_PDF_BYTES:
        path.unlink(missing_ok=True)
        raise BusinessError(t("pdf_limit"))
    try:
        await preview(path)
    except ValueError:
        path.unlink(missing_ok=True)
        raise
    await state.update_data(
        draft={"pdf_file_id": doc.file_id, "pdf_path": str(path)},
        field_index=0,
        suggested=await available_code(session),
    )
    await state.set_state(AddTest.fields)
    await prompt(message, state, session)


async def prompt(message, state, session: AsyncSession) -> None:
    """Ask for the current field using centralized texts."""
    data = await state.get_data()
    field = FIELDS[data["field_index"]]
    channels = (await session.scalars(select(Channel).order_by(Channel.id))).all()
    extra = {"code": "auto", "end_at": "unlimited_btn", "referral_enabled": "enable"}.get(field)
    keyboard = input_menu(extra=extra)
    if field == "referral_enabled":
        from aiogram.types import KeyboardButton

        keyboard.keyboard.insert(1, [KeyboardButton(text=t("disable"))])
    await message.answer(
        t(
            "prompt_" + field,
            code=data["suggested"],
            channels="\n".join(f"{c.id}: {c.title}" for c in channels),
        ),
        reply_markup=keyboard,
    )


async def field_value(message, state, session: AsyncSession) -> None:
    """Validate one value, advance and show the final preview."""
    data = await state.get_data()
    draft = data["draft"]
    field = FIELDS[data["field_index"]]
    value = (message.text or "").strip()
    if field == "title":
        if not 1 <= len(value) <= 200:
            raise BusinessError(t("invalid"))
    elif field == "code":
        value = await available_code(session) if value in ("-", t("auto")) else value
        if not re.fullmatch(r"[1-9][0-9]{3}", value):
            raise BusinessError(t("invalid"))
        if await session.scalar(
            select(Test.id).where(Test.code == value, Test.status.in_(("draft", "active")))
        ):
            raise BusinessError(t("duplicate_code"))
    elif field == "referral_enabled":
        if value not in (t("enable"), t("disable")):
            raise BusinessError(t("invalid"))
        value = value == t("enable")
    elif field == "description":
        value = "" if value == "-" else value
        if len(value) > 1000:
            raise BusinessError(t("invalid"))
    elif field == "answer_key":
        value = parse_key(value, int(draft["questions_count"])).answers
    elif field == "end_at":
        parsed = parse_date("cheksiz" if value == t("unlimited_btn") else value)
        value = parsed.isoformat() if parsed else None
    else:
        if field == "referral_count" and value == "-":
            value = str(await get(session, "referral_default"))
        value = int(value)
        low, high = {
            "questions_count": (1, 1000),
            "prizes_count": (0, 100),
            "referral_count": (0, 1000),
            "max_attempts": (1, 100),
            "channel_id": (1, 2**31),
        }[field]
        if not low <= value <= high:
            raise BusinessError(t("invalid"))
        if field == "channel_id" and await session.get(Channel, value) is None:
            raise BusinessError(t("channel_error"))
    if field == "referral_enabled":
        draft["referral_required"] = value
        if not value:
            draft["referral_count"] = 0
    else:
        draft[field] = value
    next_index = data["field_index"] + (2 if field == "referral_enabled" and not value else 1)
    await state.update_data(draft=draft, field_index=next_index)
    if next_index < len(FIELDS):
        await prompt(message, state, session)
    else:
        await state.set_state(AddTest.confirm)
        test = Test(
            **{
                **draft,
                "end_at": datetime.fromisoformat(draft["end_at"]) if draft["end_at"] else None,
            },
            created_by=message.from_user.id,
        )
        channel = await session.get(Channel, draft["channel_id"])
        await message.answer_photo(
            BufferedInputFile(await preview(draft["pdf_path"]), filename="preview.jpg"),
            caption=caption(test, channel),
            reply_markup=buttons(
                [
                    ("publish", "new:publish"),
                    ("schedule", "new:schedule"),
                    ("send_me", "new:send_me"),
                    ("edit", "new:edit"),
                    ("cancel", "new:cancel"),
                ]
            ),
            parse_mode=None,
        )


async def confirm(callback, state, session: AsyncSession) -> int:
    """Persist a draft only after preview confirmation."""
    data = await state.get_data()
    if await state.get_state() != AddTest.confirm.state or not data.get("draft"):
        raise BusinessError(t("invalid"))
    draft = data["draft"]
    draft["end_at"] = datetime.fromisoformat(draft["end_at"]) if draft["end_at"] else None
    draft["referral_required"] = draft["referral_count"] > 0
    draft["show_key_after_close"] = await get(session, "show_key_after_close")
    row = Test(**draft, created_by=callback.from_user.id, status="draft")
    try:
        async with session.begin_nested():
            session.add(row)
            await session.flush()
    except IntegrityError as exc:
        raise BusinessError(t("duplicate_code")) from exc
    await state.clear()
    return row.id


async def available_code(session: AsyncSession) -> str:
    """Choose an unused four-digit code; database uniqueness handles races."""
    used = set(
        (await session.scalars(select(Test.code).where(Test.status.in_(("draft", "active"))))).all()
    )
    available = [str(number) for number in range(1000, 10000) if str(number) not in used]
    if not available:
        raise BusinessError(t("codes_full"))
    return secrets.choice(available)
