"""Directed owner settings and membership management."""

from typing import Any

from sqlalchemy import select

from app.config import settings
from app.db.models import Admin, Channel
from app.keyboards.reply import build, choices_keyboard, input_menu
from app.menus import MENUS
from app.services import admin_service as admins
from app.services import settings_service
from app.services.errors import BusinessError
from app.services.menu_service import show
from app.texts import t

PREFIX = "Settings:"


def protected(row: Admin) -> bool:
    """Keep bootstrap administrators and owners recoverable."""
    return row.role == "owner" or row.tg_id in settings.admins


async def action(message: Any, state: Any, session: Any, bot: Any, user: Any, key: str) -> None:
    """Start one owner operation without accepting command grammar."""

    await admins.require(session, user.tg_id, "settings")
    parent = MENUS[key].parent
    await state.update_data(nav_menu=parent)
    setting = MENUS[key].setting
    if setting:
        await settings_service.set_value(
            session, setting, not await settings_service.get(session, setting)
        )
        await show(message, state, session, user, "settings")
        return
    if key in ("add_channel", "add_admin"):
        await state.set_state(PREFIX + key)
        await message.answer(
            t("channel_target" if key == "add_channel" else "admin_target"),
            reply_markup=input_menu(),
        )
        return
    channels = key.endswith("channel") or key.endswith("channels")
    model = Channel if channels else Admin
    rows = list((await session.scalars(select(model).order_by(model.id))).all())
    deleting = key.startswith("del_")
    if deleting and not channels:
        rows = [row for row in rows if not protected(row)]
    choices = {
        t("channel_item", id=row.id, title=row.title)
        if channels
        else t("admin_item", tg_id=row.tg_id, role=row.role): row.id
        for row in rows
    }
    if not choices:
        await message.answer(t("empty"), reply_markup=input_menu())
        return
    if deleting:
        await state.update_data(settings_choices=choices, settings_page=0)
        await state.set_state(PREFIX + key)
        await message.answer(t(MENUS[key].title), reply_markup=choices_keyboard(list(choices)))
    else:
        await message.answer("\n".join(choices), reply_markup=input_menu())


async def handle(message: Any, state: Any, session: Any, bot: Any, user: Any) -> bool:
    """Validate each answer against live owner permission and server choices."""

    current = await state.get_state()
    if not current or not current.startswith(PREFIX):
        return False
    await admins.require(session, user.tg_id, "settings")
    data = await state.get_data()
    text = (message.text or "").strip()
    if current in (PREFIX + "del_channel", PREFIX + "del_admin") and text in (
        t("next_page"),
        t("previous_page"),
    ):
        labels = list(data["settings_choices"])
        page = data.get("settings_page", 0) + (1 if text == t("next_page") else -1)
        page = max(0, min(page, (len(labels) - 1) // 8))
        await state.update_data(settings_page=page)
        await message.answer(t("nav_prompt"), reply_markup=choices_keyboard(labels, page))
        return True
    if current == PREFIX + "add_channel":
        await admins.add_channel(session, bot, text)
    elif current == PREFIX + "add_admin":
        if not text.isdecimal() or not 0 < int(text) < 2**63:
            raise BusinessError(t("admin_target"))
        row = await session.scalar(select(Admin).where(Admin.tg_id == int(text)))
        if row and protected(row):
            raise BusinessError(t("protected_admin"))
        await state.update_data(admin_target=int(text))
        await state.set_state(PREFIX + "role")
        await message.answer(
            t("admin_role"),
            reply_markup=build(["role_admin", "role_moderator", "back", "cancel_input"]),
        )
        return True
    elif current == PREFIX + "role":
        roles = {t("role_admin"): "admin", t("role_moderator"): "moderator"}
        if text not in roles:
            raise BusinessError(t("admin_role"))
        row = await session.scalar(
            select(Admin).where(Admin.tg_id == data["admin_target"]).with_for_update()
        )
        if row and protected(row):
            raise BusinessError(t("protected_admin"))
        if row is None:
            row = Admin(tg_id=data["admin_target"], added_by=user.tg_id)
            session.add(row)
        row.role = roles[text]
        await session.flush()
    else:
        row_id = data.get("settings_choices", {}).get(text)
        if row_id is None:
            raise BusinessError(t("invalid"))
        if current == PREFIX + "del_channel":
            await admins.remove_channel(session, row_id)
        elif current == PREFIX + "del_admin":
            row = await session.get(Admin, row_id, with_for_update=True)
            if row is None or protected(row):
                raise BusinessError(t("protected_admin"))
            await session.delete(row)
            await session.flush()
    parent = data["nav_menu"]
    await state.clear()
    await show(message, state, session, user, parent)
    return True
