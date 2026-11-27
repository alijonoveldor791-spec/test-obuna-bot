"""Role-aware menu rendering shared by conversation services."""

from typing import Any

from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User
from app.keyboards import reply
from app.menus import MENUS, permissions_for
from app.services import admin_service, settings_service
from app.services import test_manage_service as management
from app.texts import t


def button_key(text: str, menu_id: str | None = None) -> str | None:
    """Resolve only Uzbek menu text and setting indicators."""
    local = [key for key, entry in MENUS.items() if entry.parent == menu_id] if menu_id else []
    ordered = local + [key for key, entry in MENUS.items() if entry.visible and key not in local]
    ordered += [key for key, entry in MENUS.items() if not entry.visible and key not in local]
    for key in (*ordered, "back", "home", "cancel_input"):
        if key in ("user", "admin"):
            continue
        label = t(MENUS[key].title if key in MENUS else key)
        variants = {label}
        if key in MENUS and MENUS[key].setting:
            variants.update(
                t("setting_label", label=label, status=t(status))
                for status in ("setting_on", "setting_off")
            )
        if text in variants:
            return key
    return None


async def show(
    message: Any,
    state: FSMContext,
    session: AsyncSession,
    user: User,
    destination: str | None = None,
) -> None:
    """Render a declared menu, checking role again before exposing any buttons."""
    role = await admin_service.role(session, user.tg_id)
    data = await state.get_data()
    destination = destination or data.get("nav_menu") or ("admin" if role else "user")
    if destination not in MENUS:
        destination = "admin" if role else "user"
    entry = MENUS[destination]
    if destination in ("test_card", "test_list"):
        renderer = management.card if destination == "test_card" else management.list_page
        await renderer(message, state, session, user)
        return
    for permission in permissions_for(destination):
        await admin_service.require(session, user.tg_id, permission)
    user.lang = "uz"
    keyboard = reply.menu_keyboard(destination, role)
    for row in keyboard.keyboard:
        for button in row:
            key = button_key(button.text)
            if key and key in MENUS and MENUS[key].setting:
                value = await settings_service.get(session, MENUS[key].setting)
                button.text = t(
                    "setting_label",
                    label=button.text,
                    status=t("setting_on" if value else "setting_off"),
                )
    await state.update_data(nav_menu=destination)
    await message.answer(t(entry.title), reply_markup=keyboard)
