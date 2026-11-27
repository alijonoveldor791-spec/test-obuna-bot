"""Reply-only directed broadcast composition and confirmation."""

from typing import Any
from urllib.parse import urlsplit

from sqlalchemy import func, select

from app.db.models import Broadcast, Test
from app.keyboards.reply import build, choices_keyboard, input_menu
from app.services.admin_service import require
from app.services.broadcast_service import audience_query
from app.services.errors import BusinessError
from app.services.menu_service import show
from app.texts import t

PREFIX = "Broadcast:"


async def start(message: Any, state: Any, session: Any, user: Any, key: str) -> None:
    """Choose an audience using declared buttons, then a test when necessary."""
    await require(session, user.tg_id, "broadcast")
    audience = {"all_btn": "all", "participants_btn": "participants", "pending_btn": "pending"}[key]
    await state.update_data(nav_menu="broadcast", broadcast={"audience": audience})
    if audience == "all":
        await state.set_state(PREFIX + "content")
        await message.answer(t("broadcast_text"), reply_markup=input_menu())
        return
    rows = list((await session.scalars(select(Test).order_by(Test.id.desc()))).all())
    choices = {
        t("broadcast_test_item", id=row.id, code=row.code, title=row.title): row.id for row in rows
    }
    await state.update_data(broadcast_tests=choices, broadcast_page=0)
    await state.set_state(PREFIX + "test")
    await message.answer(
        t("broadcast_choice") if choices else t("empty"),
        reply_markup=choices_keyboard(list(choices)),
    )


def outgoing(draft: dict) -> str:
    """Render the exact plain text that recipients receive."""
    text = draft["text"]
    if draft.get("button_url"):
        text += "\n" + t("broadcast_link", label=draft["button_text"], url=draft["button_url"])
    return text


async def preview(message: Any, state: Any, session: Any) -> None:
    """Persist a draft only after validating the final Telegram payload."""
    draft = (await state.get_data())["broadcast"]
    text = outgoing(draft)
    if len(text.encode("utf-16-le")) // 2 > (1024 if draft.get("media_file_id") else 4096):
        raise BusinessError(t("invalid"))
    row = Broadcast(**draft)
    session.add(row)
    await session.flush()
    row.total = await session.scalar(
        select(func.count()).select_from(audience_query(row).subquery())
    )
    if row.media_file_id:
        await message.answer_photo(row.media_file_id, caption=text, parse_mode=None)
    else:
        await message.answer(text, parse_mode=None)
    await state.update_data(broadcast_id=row.id)
    await state.set_state(PREFIX + "confirm")
    await message.answer(
        t("broadcast_confirm"), reply_markup=build(["broadcast_send", "broadcast_cancel", "back"])
    )


async def discard(state: Any, session: Any) -> None:
    """Cancel an unsent persisted preview when navigation interrupts composition."""
    data = await state.get_data()
    if data.get("broadcast_id"):
        row = await session.get(Broadcast, data["broadcast_id"], with_for_update=True)
        if row and row.status == "draft":
            row.status = "cancelled"


async def handle(message: Any, state: Any, session: Any, user: Any) -> bool:
    """Consume only directed composer answers and explicit confirmation buttons."""

    current = await state.get_state()
    if not current or not current.startswith(PREFIX):
        return False
    await require(session, user.tg_id, "broadcast")
    data = await state.get_data()
    draft = data["broadcast"]
    text = message.text or ""
    step = current.removeprefix(PREFIX)
    if text == t("broadcast_cancel"):
        await discard(state, session)
        await state.clear()
        await show(message, state, session, user, "broadcast")
        return True
    if step == "test" and text in (t("next_page"), t("previous_page")):
        labels = list(data["broadcast_tests"])
        page = data.get("broadcast_page", 0) + (1 if text == t("next_page") else -1)
        page = max(0, min(page, (len(labels) - 1) // 8))
        await state.update_data(broadcast_page=page)
        await message.answer(t("broadcast_choice"), reply_markup=choices_keyboard(labels, page))
        return True
    if step == "test":
        test_id = data.get("broadcast_tests", {}).get(text)
        if not test_id or await session.get(Test, test_id) is None:
            raise BusinessError(t("no_test"))
        draft["test_id"] = test_id
        await state.update_data(broadcast=draft)
        await state.set_state(PREFIX + "content")
        await message.answer(t("broadcast_text"), reply_markup=input_menu())
    elif step == "content":
        content = message.caption if message.photo else text
        if not content or len(content.encode("utf-16-le")) // 2 > (1024 if message.photo else 4096):
            raise BusinessError(t("invalid"))
        draft.update(
            text=content, media_file_id=message.photo[-1].file_id if message.photo else None
        )
        await state.update_data(broadcast=draft)
        await state.set_state(PREFIX + "link")
        await message.answer(
            t("broadcast_button"),
            reply_markup=build(["broadcast_add_link", "broadcast_no_link", "back", "cancel_input"]),
        )
    elif step == "link":
        if text == t("broadcast_no_link"):
            await preview(message, state, session)
        elif text == t("broadcast_add_link"):
            await state.set_state(PREFIX + "label")
            await message.answer(t("broadcast_label"), reply_markup=input_menu())
        else:
            raise BusinessError(t("invalid"))
    elif step == "label":
        if not 1 <= len(text.strip()) <= 64:
            raise BusinessError(t("invalid"))
        draft["button_text"] = text.strip()
        await state.update_data(broadcast=draft)
        await state.set_state(PREFIX + "url")
        await message.answer(t("broadcast_url"), reply_markup=input_menu())
    elif step == "url":
        try:
            url = urlsplit(text)
            valid = (
                url.scheme == "https"
                and url.hostname
                and not url.username
                and not url.password
                and not any(c.isspace() or ord(c) < 32 for c in text)
            )
        except ValueError:
            valid = False
        if not valid:
            raise BusinessError(t("broadcast_url"))
        draft["button_url"] = text
        await state.update_data(broadcast=draft)
        await preview(message, state, session)
    elif step in ("confirm", "running"):
        row = await session.get(Broadcast, data["broadcast_id"], with_for_update=True)
        if row is None:
            raise BusinessError(t("empty"))
        if step == "confirm" and text == t("broadcast_send") and row.status == "draft":
            row.status = "running"
            await state.set_state(PREFIX + "running")
        elif step == "running" and text == t("broadcast_stop") and row.status == "running":
            row.status = "cancelled"
        elif step != "running" or text != t("broadcast_status"):
            raise BusinessError(t("invalid"))
        await message.answer(
            t(
                "broadcast_progress",
                id=row.id,
                status=row.status,
                total=row.total,
                sent=row.sent,
                failed=row.failed,
            ),
            reply_markup=build(["broadcast_status", "broadcast_stop", "back", "home"]),
        )
    return True
