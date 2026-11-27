"""Transactional grading and answer-key revisions."""

from datetime import UTC

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import utcnow
from app.db.models import Submission, Test, User
from app.repositories.submissions import attempts as attempt_count
from app.services.answer_parser import parse_answers, parse_key
from app.services.errors import BusinessError
from app.services.ranking_service import recalculate
from app.services.referral_service import count
from app.services.test_time_service import aware, display
from app.texts import t


class GradingError(BusinessError):
    """Attempt cannot be accepted."""


def active(test: Test) -> bool:
    """Check publication and deadline using aware timestamps."""
    deadline = test.end_at
    if deadline and deadline.tzinfo is None:
        deadline = deadline.replace(tzinfo=UTC)
    return (
        test.status == "active"
        and test.start_at is not None
        and aware(test.start_at) <= utcnow()
        and (deadline is None or deadline > utcnow())
    )


def score(answers: dict[str, str], key: dict[str, str]) -> tuple[int, int, float]:
    """Calculate public totals without exposing the key."""
    correct = sum(answers.get(number) == answer for number, answer in key.items())
    return correct, len(key) - correct, round(correct / len(key) * 100, 2) if key else 0.0


async def submit(session: AsyncSession, user: User, text: str) -> tuple[Submission, Test, bool]:
    """Serialize attempts on the test row to enforce attempt limits."""
    if len(text.strip()) == 4 and text.strip().isdigit():
        scheduled = await session.scalar(
            select(Test)
            .where(Test.code == text.strip(), Test.status.in_(("draft", "active")))
            .limit(1)
        )
        if scheduled and scheduled.start_at and aware(scheduled.start_at) > utcnow():
            raise GradingError(t("not_started", start=display(scheduled.start_at)))
    parsed = parse_answers(text)
    query = select(Test)
    if parsed.code:
        query = query.where(Test.code == parsed.code).order_by(
            (Test.status == "active").desc(), (Test.status == "draft").desc(), Test.id.desc()
        )
    else:
        query = query.where(
            Test.status == "active",
            Test.start_at <= utcnow(),
            or_(Test.end_at.is_(None), Test.end_at > utcnow()),
        ).order_by(Test.start_at.desc(), Test.id.desc())
    test = await session.scalar(query.limit(1).with_for_update())
    if test is not None and test.start_at and aware(test.start_at) > utcnow():
        raise GradingError(t("not_started", start=display(test.start_at)))
    if test is not None and test.status == "closed":
        raise GradingError(t("test_closed"))
    if test is None or not active(test):
        raise GradingError(t("no_test"))
    await session.refresh(user)
    if user.is_banned:
        raise GradingError(t("denied"))
    attempts = await attempt_count(session, test.id, user.id)
    if attempts >= 1:
        raise GradingError(t("attempts"))
    referrals = await count(session, user.id, test)
    if test.referral_required and referrals < test.referral_count:
        raise GradingError(
            t("ref_needed", count=referrals, required=test.referral_count, link=t("referral"))
        )
    answers = parse_answers(text, test.questions_count).answers
    correct, wrong, percent = score(answers, test.answer_key)
    row = Submission(
        test_id=test.id,
        user_id=user.id,
        attempt_no=attempts + 1,
        answers=answers,
        correct_count=correct,
        wrong_count=wrong,
        score_percent=percent,
    )
    session.add(row)
    await session.flush()
    await recalculate(session, test.id)
    return row, test, parsed.code is None


async def change_key(session: AsyncSession, test_id: int, text: str) -> None:
    """Regrade every attempt under the same lock used by submissions."""
    test = await session.scalar(select(Test).where(Test.id == test_id).with_for_update())
    test.answer_key = parse_key(text, test.questions_count).answers
    for row in (
        await session.scalars(select(Submission).where(Submission.test_id == test_id))
    ).all():
        row.correct_count, row.wrong_count, row.score_percent = score(row.answers, test.answer_key)
    await recalculate(session, test_id)
