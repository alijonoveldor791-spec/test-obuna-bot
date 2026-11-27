"""Inline keyboard reserved for subscription checking."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.texts import t


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
