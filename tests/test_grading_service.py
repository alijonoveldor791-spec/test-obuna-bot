"""Scoring, attempts, expiry, referral requirements and regrading."""

from datetime import timedelta

import pytest
from sqlalchemy import select

from app.db.base import utcnow
from app.db.models import Submission, Test, User
from app.services.grading_service import GradingError, active, change_key, score, submit


async def setup(db, **overrides):
    user = User(tg_id=101, full_name="Ali")
    db.add(user)
    values = dict(
        code="4829",
        title="Math",
        pdf_file_id="pdf",
        pdf_path="x.pdf",
        questions_count=2,
        answer_key={"1": "a", "2": "b"},
        created_by=1,
        status="active",
        start_at=utcnow(),
        max_attempts=1,
    )
    values.update(overrides)
    test = Test(**values)
    db.add(test)
    await db.flush()
    return user, test


async def test_grade_and_limit(db):
    user, test = await setup(db)
    row, selected, implicit = await submit(db, user, "4829 aa")
    assert (row.correct_count, row.wrong_count, row.score_percent, row.rank) == (1, 1, 50, 1)
    assert selected.id == test.id and not implicit
    with pytest.raises(GradingError):
        await submit(db, user, "4829 ab")


async def test_regrade(db):
    user, test = await setup(db, max_attempts=2)
    first, _, _ = await submit(db, user, "aa")
    second, _, _ = await submit(db, user, "ab")
    assert first.rank is None and second.rank == 1
    await change_key(db, test.id, "1a,2a")
    assert first.rank == 1 and first.correct_count == 2 and second.rank is None


@pytest.mark.parametrize(
    "values",
    [
        {"status": "closed"},
        {"end_at": utcnow() - timedelta(seconds=1)},
        {"referral_required": True, "referral_count": 2},
    ],
)
async def test_rejections(db, values):
    user, _ = await setup(db, **values)
    with pytest.raises(GradingError):
        await submit(db, user, "ab")
    assert not list((await db.scalars(select(Submission))).all())


async def test_banned_and_missing(db):
    user, test = await setup(db)
    user.is_banned = True
    await db.flush()
    with pytest.raises(GradingError):
        await submit(db, user, "ab")
    with pytest.raises(GradingError):
        await submit(db, user, "9999 ab")
    assert score({}, {}) == (0, 0, 0)
    test.status = "paused"
    assert not active(test)
