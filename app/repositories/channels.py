"""Channel lookup queries."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Channel


async def required(session: AsyncSession) -> list[Channel]:
    """Return subscription-required channels in a stable order."""
    return list(
        (
            await session.scalars(
                select(Channel).where(Channel.is_required.is_(True)).order_by(Channel.id)
            )
        ).all()
    )
