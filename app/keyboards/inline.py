"""Administrator inline navigation."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.constants import MAX_CALLBACK_BYTES
from app.services.admin_service import PERMISSIONS
from app.texts import t


def buttons(items: list[tuple[str, str]]) -> InlineKeyboardMarkup:
    """Create one translated callback button per row."""
    if any(len(data.encode("utf-8")) > MAX_CALLBACK_BYTES for _, data in items):
        raise ValueError("Callback data exceeds Telegram limit")
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t(label), callback_data=data)] for label, data in items
        ]
    )


def test_card(test_id: int, role: str) -> InlineKeyboardMarkup:
    """Build test actions with consistent permission visibility."""
    items = [
        ("ranking", f"t:ranking:{test_id}"),
        ("stats", f"t:stats:{test_id}"),
        ("export_results", f"exp:results:{test_id}"),
        ("export_access", f"exp:access:{test_id}"),
    ]
    if "tests" in PERMISSIONS.get(role, set()):
        items += [
            (name, f"t:{action}:{test_id}")
            for name, action in (
                ("publish", "publish"),
                ("send_me", "send_me"),
                ("schedule", "schedule"),
                ("pause", "pause"),
                ("resume", "resume"),
                ("close", "close"),
                ("key", "key"),
                ("description", "description"),
                ("deadline", "deadline"),
                ("delete", "delete"),
                ("winners", "winners"),
            )
        ]
    return buttons(items)


def subscriptions(channels, lang: str = "uz") -> InlineKeyboardMarkup:
    """Link missing channels and explicit refresh callback."""
    rows = [
        [
            InlineKeyboardButton(
                text=c.title, url=f"https://t.me/{c.username}" if c.username else c.invite_link
            )
        ]
        for c in channels
        if c.username or c.invite_link
    ]
    rows.append([InlineKeyboardButton(text=t("check", lang), callback_data="sub:check")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
