"""Atomic invitation attribution and subscription validation."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Referral, User
from app.repositories.referrals import valid_count


async def attribute(session: AsyncSession, user: User, inviter_tg: int, is_new: bool) -> bool:
    """Attribute only the first start of a new, different participant."""
    if not is_new or user.tg_id == inviter_tg:
        return False
    inviter = await session.scalar(select(User).where(User.tg_id == inviter_tg))
    if not inviter or await session.scalar(
        select(Referral.id).where(Referral.invited_id == user.id)
    ):
        return False
    user.referrer_id = inviter.id
    session.add(Referral(inviter_id=inviter.id, invited_id=user.id, is_valid=False))
    await session.flush()
    return True


async def validate(session: AsyncSession, user: User, subscribed: bool) -> bool:
    """Return whether an invitation became valid now."""
    referral = await session.scalar(
        select(Referral).where(Referral.invited_id == user.id).with_for_update()
    )
    if referral is None:
        return False
    changed = subscribed and not referral.is_valid
    referral.is_valid = subscribed
    await session.flush()
    return changed


async def count(session: AsyncSession, user_id: int) -> int:
    """Count currently subscribed invitations."""
    return await valid_count(session, user_id)
