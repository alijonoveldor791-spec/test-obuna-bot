"""Database-backed operational notifications."""

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Admin


async def notify_admins(bot: Bot, session: AsyncSession, text: str) -> None:
    """Notify current owners/admins, isolating unavailable recipients."""
    recipients = (
        await session.scalars(select(Admin.tg_id).where(Admin.role.in_(("owner", "admin"))))
    ).all()
    for tg_id in recipients:
        try:
            await bot.send_message(tg_id, text, parse_mode=None)
        except TelegramAPIError:
            continue
