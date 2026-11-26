"""User interactions with subscription continuation."""

from sqlalchemy import select

from app.config import settings
from app.db.models import AccessLog, Submission, Test
from app.keyboards.user import menu, subscriptions
from app.repositories.tests import latest
from app.services import referral_service, subscription_service
from app.services.grading_service import active, submit
from app.services.settings_service import get
from app.texts import t
from app.utils.deeplink import link


async def gate(
    message, state, session, bot, redis, user, action: str, payload=None, force: bool = False
) -> bool:
    """Store a resumable action if any required membership is missing."""
    missing = await subscription_service.check(session, bot, redis, user, force)
    if missing:
        await state.update_data(pending_action=action, pending_payload=payload)
        await message.answer(
            t("subscribe", user.lang), reply_markup=subscriptions(missing, user.lang)
        )
        return False
    await state.update_data(pending_action=None, pending_payload=None)
    return True


async def send_test(
    message, state, session, bot, redis, user, test_id: int | None = None, force=False
) -> None:
    """Check subscription, send active PDF and log a unique download."""
    if not await gate(message, state, session, bot, redis, user, "test", test_id, force):
        return
    test = await latest(session, test_id)
    if test is None or not active(test):
        await message.answer(t("no_test", user.lang))
        return
    await bot.send_document(
        user.tg_id, test.pdf_file_id, protect_content=await get(session, "protect_content")
    )
    if not await session.scalar(
        select(AccessLog.id).where(AccessLog.user_id == user.id, AccessLog.test_id == test.id)
    ):
        session.add(AccessLog(user_id=user.id, test_id=test.id))
        await session.flush()
    await message.answer(t("answer_hint", user.lang, code=test.code))


async def answers(
    message, state, session, bot, redis, user, text: str | None = None, force=False
) -> None:
    """Gate grading then return only totals."""
    text = text or message.text or ""
    if not await gate(message, state, session, bot, redis, user, "answers", text, force):
        return
    row, test, implicit = await submit(session, user, text)
    if implicit:
        await message.answer(t("implicit", user.lang, code=test.code))
    await message.answer(
        t(
            "graded",
            user.lang,
            correct=row.correct_count,
            total=test.questions_count,
            wrong=row.wrong_count,
            percent=row.score_percent,
        )
    )


async def start(message, state, session, bot, redis, user, is_new: bool) -> None:
    """Handle welcome, test deep links and first-start invitation attribution."""
    payload = (message.text or "").split(maxsplit=1)
    payload = payload[1] if len(payload) > 1 else ""
    if payload.startswith("ref_") and payload[4:].isdigit():
        await referral_service.attribute(session, user, int(payload[4:]), is_new)
    await message.answer(t("hello", user.lang), reply_markup=menu(user.lang))
    test_id = int(payload[5:]) if payload.startswith("test_") and payload[5:].isdigit() else None
    await send_test(message, state, session, bot, redis, user, test_id)


async def resume(callback, state, session, bot, redis, user) -> None:
    """Force-refresh membership then resume the stored operation."""
    data = await state.get_data()
    if data.get("pending_action") == "answers":
        await answers(
            callback.message,
            state,
            session,
            bot,
            redis,
            user,
            data.get("pending_payload"),
            force=True,
        )
    else:
        await send_test(
            callback.message,
            state,
            session,
            bot,
            redis,
            user,
            data.get("pending_payload"),
            force=True,
        )


async def my_results(message, session, user, page: int = 0) -> None:
    """Display paged attempt history."""
    rows = (
        await session.execute(
            select(Submission, Test.code)
            .join(Test, Test.id == Submission.test_id)
            .where(Submission.user_id == user.id)
            .order_by(Submission.submitted_at.desc())
            .offset(page * 20)
            .limit(20)
        )
    ).all()
    await message.answer(
        "\n".join(
            t(
                "result_row",
                user.lang,
                code=code,
                correct=row.correct_count,
                percent=row.score_percent,
            )
            for row, code in rows
        )
        or t("empty", user.lang)
    )


async def referral(message, session, user) -> None:
    """Display personal invitation link and current progress."""
    await message.answer(
        t(
            "ref_link",
            user.lang,
            link=link(settings.bot_username, f"ref_{user.tg_id}"),
            count=await referral_service.count(session, user.id),
        )
    )

    test = await latest(session)
    if test and test.referral_required:
        await message.answer(t("ref_progress", user.lang,
                               count=await referral_service.count(session, user.id),
                               required=test.referral_count))
