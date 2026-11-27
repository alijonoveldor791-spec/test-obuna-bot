"""Participant persistence."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import utcnow
from app.db.models import User


async def upsert(session: AsyncSession, telegram_user) -> tuple[User, bool]:
    """Create or update one Telegram participant under a transaction lock."""
    user = await session.scalar(
        select(User).where(User.tg_id == telegram_user.id).with_for_update()
    )
    new = user is None
    if user is None:
        user = User(tg_id=telegram_user.id, full_name=telegram_user.full_name[:256])
        session.add(user)
    user.username = telegram_user.username
    user.full_name = telegram_user.full_name[:256]
    user.is_blocked = False
    user.last_active = utcnow()
    await session.flush()
    return user, new
