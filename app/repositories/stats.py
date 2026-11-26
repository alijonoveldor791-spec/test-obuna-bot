"""Aggregate participant and test statistics."""

from datetime import timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import utcnow
from app.db.models import AccessLog, Referral, Submission, Test, User


async def general(session: AsyncSession) -> dict:
    """Count growth using Tashkent calendar boundaries."""
    now = utcnow().astimezone(ZoneInfo("Asia/Tashkent"))
    day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    result = {}
    for key, start in (
        ("total", None),
        ("today", day),
        ("week", day - timedelta(days=now.weekday())),
        ("month", day.replace(day=1)),
    ):
        query = select(func.count()).select_from(User)
        if start:
            query = query.where(User.joined_at >= start)
        result[key] = await session.scalar(query) or 0
    result["left"] = (
        await session.scalar(
            select(func.count()).select_from(User).where(User.left_channel_at.is_not(None))
        )
        or 0
    )
    rows = (
        await session.execute(
            select(User.full_name, func.count(Referral.id))
            .join(Referral, Referral.inviter_id == User.id)
            .where(Referral.is_valid.is_(True))
            .group_by(User.id, User.full_name)
            .order_by(func.count(Referral.id).desc())
            .limit(10)
        )
    ).all()
    result["refs"] = "\n".join(f"{name}: {count}" for name, count in rows) or "?"
    return result


async def for_test(session: AsyncSession, test: Test) -> dict:
    """Count unique participants, best scores and per-question accuracy."""
    rows = list(
        (
            await session.scalars(
                select(Submission).where(
                    Submission.test_id == test.id, Submission.rank.is_not(None)
                )
            )
        ).all()
    )
    return {
        "access": await session.scalar(
            select(func.count()).select_from(AccessLog).where(AccessLog.test_id == test.id)
        )
        or 0,
        "submitted": len(rows),
        "average": sum(row.score_percent for row in rows) / len(rows) if rows else 0,
        "questions": "\n".join(
            f"{number}: {sum(row.answers.get(number) == answer for row in rows) / len(rows) * 100 if rows else 0:.1f}%"
            for number, answer in test.answer_key.items()
        ),
    }
