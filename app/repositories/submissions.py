"""Submission lookup queries."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Submission


async def attempts(session: AsyncSession, test_id: int, user_id: int) -> int:
    """Count attempts while the caller holds the parent-test lock."""
    return (
        await session.scalar(
            select(func.count())
            .select_from(Submission)
            .where(Submission.test_id == test_id, Submission.user_id == user_id)
        )
        or 0
    )
