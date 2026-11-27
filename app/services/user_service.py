"""User interactions with subscription continuation."""

from html import escape
from typing import Any

from aiogram.fsm.context import FSMContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.base import utcnow
from app.db.models import AccessLog, Submission, Test
from app.keyboards.inline import subscriptions
from app.keyboards.reply import input_menu
from app.keyboards.reply import user_menu as menu
from app.repositories.tests import latest
from app.services import referral_service, subscription_service
from app.services.grading_service import active, submit
from app.services.settings_service import get
from app.services.test_time_service import aware, display
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
    requested = await latest(session, test_id) if test_id else None
    if requested and requested.start_at and aware(requested.start_at) > utcnow():
        await message.answer(t("not_started", start=display(requested.start_at)))
        return
    test = await latest(session)
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
    await message.answer(
        t(
            "answer_hint",
            code=test.code,
            questions=test.questions_count,
            sample=answer_sample(test),
        ),
        reply_markup=menu(),
        parse_mode="HTML",
    )


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
    requested = int(payload[5:]) if payload.startswith("test_") and payload[5:].isdigit() else None
    await send_test(message, state, session, bot, redis, user, requested)


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
        "\n\n".join(
            t(
                "result_row",
                user.lang,
                code=code,
                correct=row.correct_count,
                percent=row.score_percent,
            )
            for row, code in rows
        )
        or t("no_results"),
        reply_markup=menu(),
        parse_mode=None,
    )


async def referral(message, session, user) -> None:
    """Explain one test's referral requirement and progress in a single message."""
    test = await latest(session)
    count = await referral_service.count(session, user.id, test)
    if test and test.referral_required:
        progress = t(
            "ref_ready" if count >= test.referral_count else "ref_progress",
            title=test.title,
            count=count,
            required=test.referral_count,
            remaining=max(0, test.referral_count - count),
        )
    else:
        progress = t("ref_optional" if test else "ref_no_test", count=count)
    await message.answer(
        t("ref_link", link=link(settings.bot_username, f"ref_{user.tg_id}"), progress=progress),
        reply_markup=menu(),
        parse_mode=None,
    )


async def answer_instructions(message: Any, state: FSMContext, session: AsyncSession) -> None:
    """Use the current test's real code and size in participant instructions."""
    test = await latest(session)
    if test is None:
        await state.set_state(None)
        await message.answer(t("no_test"), reply_markup=menu())
        return
    await state.set_state("Navigation:answers")
    await message.answer(
        t(
            "answer_prompt",
            title=escape(test.title),
            code=test.code,
            questions=test.questions_count,
            sample=answer_sample(test),
        ),
        reply_markup=input_menu(),
        parse_mode="HTML",
    )


def answer_sample(test: Test) -> str:
    """Build copyable placeholders without reading the private answer key."""
    # Keep even the largest supported test inside Telegram's message limit.
    count = min(test.questions_count, 100)
    values = ",".join(f"{number}?" for number in range(1, count + 1))
    if count < test.questions_count:
        values += ",..."
    return escape(f"{test.code} {values}")
