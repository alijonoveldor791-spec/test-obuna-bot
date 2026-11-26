"""Deterministic ranking, using each participant's best attempt."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Submission


async def recalculate(session: AsyncSession, test_id: int) -> list[Submission]:
    """Rank best attempts by score then submission time and ID."""
    rows = list(
        (
            await session.scalars(
                select(Submission)
                .where(Submission.test_id == test_id)
                .order_by(Submission.correct_count.desc(), Submission.submitted_at, Submission.id)
            )
        ).all()
    )
    seen = set()
    best = []
    for row in rows:
        row.rank = None
        if row.user_id not in seen:
            seen.add(row.user_id)
            best.append(row)
            row.rank = len(best)
    await session.flush()
    return best
