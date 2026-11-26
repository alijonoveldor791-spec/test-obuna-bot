"""Test lookup queries."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Test


async def latest(session: AsyncSession, test_id: int | None = None) -> Test | None:
    """Find the last published active test, or a specific test."""
    query = select(Test)
    if test_id is not None:
        query = query.where(Test.id == test_id)
    else:
        query = query.where(Test.status == "active", Test.start_at.is_not(None)).order_by(
            Test.start_at.desc(), Test.id.desc()
        )
    return await session.scalar(query.limit(1))
