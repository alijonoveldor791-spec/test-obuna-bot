"""Referral aggregate queries."""
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Referral


async def valid_count(session: AsyncSession,user_id: int) -> int:
    """Count invitations currently meeting subscription requirements."""
    return await session.scalar(select(func.count()).select_from(Referral).where(Referral.inviter_id==user_id,Referral.is_valid.is_(True))) or 0
