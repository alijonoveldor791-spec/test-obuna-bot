"""Referral aggregate queries."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Referral, Test, User


async def valid_count(session: AsyncSession, user_id: int, test: Test | None = None) -> int:
    """Count subscribed invitations created after this test started."""
    query = (
        select(func.count())
        .select_from(Referral)
        .join(User, User.id == Referral.invited_id)
        .where(
            Referral.inviter_id == user_id,
            Referral.is_valid.is_(True),
            User.is_subscribed.is_(True),
        )
    )
    if test is not None:
        if test.start_at is None:
            return 0
        query = query.where(Referral.created_at >= test.start_at)
    return await session.scalar(query) or 0
