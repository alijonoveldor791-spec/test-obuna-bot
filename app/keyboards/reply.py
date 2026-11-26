"""Persistent role-aware reply keyboards."""

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

from app.services.admin_service import PERMISSIONS
from app.texts import t

SECTIONS = {
    "tests": ("active", "draft", "closed", "search_code"),
    "stats": ("general", "test_stats_btn", "growth", "ref_top"),
    "results_admin": ("top10", "top50", "winners_btn", "publish_results_btn"),
    "exports": ("export_results", "export_access", "export_users", "export_refs"),
    "broadcast": ("all_btn", "participants_btn", "pending_btn", "left_btn"),
    "users": ("find_user", "ban_btn", "unban_btn", "banned_btn"),
    "channels": ("add_channel", "list_channels", "del_channel"),
    "settings": ("ref_default", "protect_btn", "reminders_btn", "key_btn", "language_btn"),
    "admins": ("add_admin", "list_admins", "del_admin"),
}
ADMIN_KEYS = (
    "new_test",
    "tests",
    "stats",
    "results_admin",
    "exports",
    "broadcast",
    "users",
    "channels",
    "settings",
    "admins",
    "user_mode",
)


def permission(key: str) -> str:
    """Map navigation to existing service permissions."""
    return {"new_test": "tests", "results_admin": "stats"}.get(key, key)


def build(keys: list[str], lang: str = "uz", footer: bool = False) -> ReplyKeyboardMarkup:
    """Translate buttons and keep navigation on its own final row."""
    rows = [
        [KeyboardButton(text=t(key, lang)) for key in keys[i : i + 2]]
        for i in range(0, len(keys), 2)
    ]
    if footer:
        rows.append([KeyboardButton(text=t(key, lang)) for key in ("back", "home")])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True, is_persistent=True)


def user_menu(lang: str = "uz") -> ReplyKeyboardMarkup:
    """Show all participant entry points."""
    return build(["latest", "submit_btn", "results", "referral", "help_btn"], lang)


def admin_menu(role: str, lang: str = "uz") -> ReplyKeyboardMarkup:
    """Hide actions outside the current administrator role."""
    return build(
        [
            key
            for key in ADMIN_KEYS
            if key == "user_mode" or permission(key) in PERMISSIONS.get(role, set())
        ],
        lang,
    )


def section_menu(section: str, lang: str = "uz") -> ReplyKeyboardMarkup:
    """Show section actions and parent navigation."""
    return build(list(SECTIONS[section]), lang, footer=True)


def input_menu(lang: str = "uz", extra: str | None = None) -> ReplyKeyboardMarkup:
    """Limit data-entry controls to optional shortcut, back and cancel."""
    return build(([extra] if extra else []) + ["back", "cancel_input"], lang)
