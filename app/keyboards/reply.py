"""Persistent role-aware reply keyboards."""

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

from app.menus import MENUS, children, permissions_for
from app.services.admin_service import PERMISSIONS
from app.texts import t

ADMIN_KEYS = MENUS["admin"].buttons
SECTIONS = {key: menu.buttons for key, menu in MENUS.items() if menu.parent and menu.buttons}


def permission(key: str) -> str | None:
    """Read the permission directly from the menu declaration."""
    return MENUS[key].permission


def build(keys: list[str], lang: str = "uz", footer: bool = False) -> ReplyKeyboardMarkup:
    """Translate buttons and keep navigation on its own final row."""
    rows = [
        [
            KeyboardButton(text=t(MENUS[key].title if key in MENUS else key))
            for key in keys[i : i + 2]
        ]
        for i in range(0, len(keys), 2)
    ]
    if footer:
        rows.append([KeyboardButton(text=t(key, lang)) for key in ("back", "home")])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True, is_persistent=True)


def menu_keyboard(menu_id: str, role: str | None = None) -> ReplyKeyboardMarkup:
    """Render permitted children and their declared parent navigation."""
    menu = MENUS[menu_id]
    allowed = PERMISSIONS.get(role, set())
    keys = [key for key in children(menu_id) if permissions_for(key) <= allowed]
    return build(keys, footer=menu.parent is not None)


def user_menu(lang: str = "uz") -> ReplyKeyboardMarkup:
    """Show participant entry points in Uzbek."""
    return menu_keyboard("user")


def admin_menu(role: str, lang: str = "uz") -> ReplyKeyboardMarkup:
    """Show role-permitted administrator entry points."""
    return menu_keyboard("admin", role)


def section_menu(section: str, lang: str = "uz", role: str | None = None) -> ReplyKeyboardMarkup:
    """Render a section from the shared declaration."""
    return menu_keyboard(section, role)


def input_menu(lang: str = "uz", extra: str | None = None) -> ReplyKeyboardMarkup:
    """Use only optional shortcuts, back and cancel during data entry."""
    return build(([extra] if extra else []) + ["back", "cancel_input"])


def choices_keyboard(labels: list[str], page: int = 0) -> ReplyKeyboardMarkup:
    """Render bounded raw labels with translated paging and input controls."""
    keyboard = input_menu()
    keyboard.keyboard[0:0] = [
        [KeyboardButton(text=label)] for label in labels[page * 8 : (page + 1) * 8]
    ]
    paging = []
    if page:
        paging.append(KeyboardButton(text=t("previous_page")))
    if (page + 1) * 8 < len(labels):
        paging.append(KeyboardButton(text=t("next_page")))
    if paging:
        keyboard.keyboard.insert(-1, paging)
    return keyboard
