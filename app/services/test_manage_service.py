"""Reply-based test listing, draft publication and guarded lifecycle actions."""

from datetime import datetime
from pathlib import Path
from typing import Any

from aiogram import Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, KeyboardButton
from sqlalchemy import event, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AccessLog, Channel, Test, User
from app.keyboards.reply import build
from app.repositories import stats
from app.services import admin_service, grading_service, post_service, ranking_service
from app.services import test_creation_service as creation
from app.services.errors import BusinessError
from app.services.export_service import test_report
from app.services.referral_service import count
from app.services.test_time_service import display
from app.states.add_test import AddTest
from app.texts import t

EDIT_STATE = "Tests:edit"
POST_INPUT = "Tests:post_text"
POST_CONFIRM = "Tests:post_confirm"
CONFIRM_STATE = "Tests:confirm"
PAGE_SIZE = 8
CARD_KEYS = {
    "draft": ("edit_post", "delete"),
    "active": ("test_stats", "excel_results", "key", "close"),
    "closed": ("test_stats", "excel_results", "announce"),
}
ACTION_PERMISSIONS = {
    "edit_post": "tests",
    "delete": "tests",
    "key": "tests",
    "close": "tests",
    "announce": "tests",
    "test_stats": "stats",
    "excel_results": "exports",
}


def allowed(test: Test) -> tuple[str, ...]:
    """Only scheduled drafts expose cancellation."""
    return CARD_KEYS[test.status] if test.status != "draft" or test.scheduled_at else ()


async def list_page(
    message: Any,
    state: FSMContext,
    session: AsyncSession,
    user: User,
    status: str | None = None,
    page: int | None = None,
) -> None:
    """Show eight server-selected test labels and persistent paging controls."""
    await admin_service.require(session, user.tg_id, "tests_view")
    data = await state.get_data()
    status = status or data.get("test_filter", "active")
    page = max(0, data.get("test_page", 0) if page is None else page)
    if status not in ("active", "closed"):
        raise BusinessError(t("invalid"))
    rows = list(
        (
            await session.scalars(
                select(Test)
                .where(
                    or_(
                        Test.status == "active",
                        (Test.status == "draft") & Test.scheduled_at.is_not(None),
                    )
                    if status == "active"
                    else Test.status == "closed"
                )
                .order_by(Test.id.desc())
                .offset(page * PAGE_SIZE)
                .limit(PAGE_SIZE + 1)
            )
        ).all()
    )
    if not rows and page:
        await list_page(message, state, session, user, status, page - 1)
        return
    labels = {
        (
            t(
                "scheduled_row",
                id=row.id,
                code=row.code,
                title=row.title[:160],
                start=display(row.start_at),
            )
            if row.status == "draft"
            else t("test_row", id=row.id, code=row.code, title=row.title[:160])
        ): row.id
        for row in rows[:PAGE_SIZE]
    }
    keyboard = build([], footer=True)
    keyboard.keyboard[0:0] = [[KeyboardButton(text=label)] for label in labels]
    paging = []
    if page:
        paging.append(KeyboardButton(text=t("previous_page")))
    if len(rows) > PAGE_SIZE:
        paging.append(KeyboardButton(text=t("next_page")))
    if paging:
        keyboard.keyboard.insert(len(keyboard.keyboard) - 1, paging)
    await state.set_state(None)
    await state.update_data(
        nav_menu="test_list", test_filter=status, test_page=page, test_choices=labels
    )
    await message.answer(t("test_list") if rows else t("empty"), reply_markup=keyboard)


async def card(
    message: Any, state: FSMContext, session: AsyncSession, user: User, test_id: int | None = None
) -> None:
    """Expose actions valid for the selected test's live status and role."""
    role = await admin_service.require(session, user.tg_id, "tests_view")
    test_id = test_id or (await state.get_data()).get("test_id")
    test = await session.get(Test, test_id) if test_id else None
    if test is None:
        raise BusinessError(t("no_test"))
    keys = [
        key for key in allowed(test) if ACTION_PERMISSIONS[key] in admin_service.PERMISSIONS[role]
    ]
    await state.set_state(None)
    context = await state.get_data()
    await state.update_data(
        nav_menu="test_card",
        test_id=test.id,
        test_filter=context.get("test_filter", "active" if test.status == "draft" else test.status),
        test_page=context.get("test_page", 0),
    )
    await message.answer(
        t(
            "card",
            title=test.title,
            code=test.code,
            status=test.status,
            questions=test.questions_count,
            deadline=display(test.end_at) if test.end_at else t("unlimited"),
        ),
        reply_markup=build(keys, footer=True),
        parse_mode=None,
    )


async def action(
    message: Any, state: FSMContext, session: AsyncSession, bot: Bot, user: User, key: str
) -> None:
    """Authorize and validate an action before collection or confirmation."""
    await admin_service.require(session, user.tg_id, ACTION_PERMISSIONS[key])
    data = await state.get_data()
    test = await session.scalar(
        select(Test).where(Test.id == data.get("test_id")).with_for_update()
    )
    if test is None:
        raise BusinessError(t("no_test"))
    if key not in allowed(test):
        raise BusinessError(t("test_changed"))
    if key == "edit_post":
        await edit_post(message, state, session, user)
    elif key in ("delete", "close", "announce"):
        await state.set_state(CONFIRM_STATE)
        await state.update_data(confirm_action=key, confirm_status=test.status)
        await message.answer(
            t("test_confirmation", action=t(key), id=test.id, code=test.code, title=test.title),
            reply_markup=build(["yes", "no", "back", "cancel_input"]),
        )
    elif key == "key":
        await state.set_state(EDIT_STATE)
        await state.update_data(edit_action=key, edit_status=test.status)
        await message.answer(t("prompt_answer_key"), reply_markup=build(["back", "cancel_input"]))
    elif key == "test_stats":
        rows = await ranking_service.recalculate(session, test.id)
        values = await stats.for_test(session, test)
        lines = []
        for row in rows[:10]:
            person = await session.get(User, row.user_id)
            lines.append(
                t(
                    "top_row",
                    rank=row.rank,
                    name=person.full_name[:80],
                    correct=row.correct_count,
                    percent=row.score_percent,
                )
            )
        completed = 0
        if test.referral_required:
            people = (
                await session.scalars(
                    select(User)
                    .join(AccessLog, AccessLog.user_id == User.id)
                    .where(AccessLog.test_id == test.id)
                )
            ).all()
            for person in people:
                completed += await count(session, person.id, test) >= test.referral_count
        await message.answer(
            t(
                "results_summary",
                **values,
                referral=t("ref_completed", count=completed) if test.referral_required else "",
                ranking="\n".join(lines) or t("empty"),
            ),
            parse_mode=None,
        )
    else:
        await ranking_service.recalculate(session, test.id)
        content = await test_report(session, test.id)
        await message.answer_document(BufferedInputFile(content, filename=f"test-{test.id}.xlsx"))


def delete_pdf_after_commit(session: AsyncSession, path: str) -> None:
    """Delete owned PDF files only after the database deletion commits."""
    target = Path(path).resolve()
    if not target.is_relative_to(Path("storage/pdf").resolve()):
        raise BusinessError(t("invalid_pdf_path"))
    sync = session.sync_session
    sync.info.setdefault("deleted_test_pdfs", set()).add(target)
    if sync.info.get("test_pdf_hooks"):
        return
    sync.info["test_pdf_hooks"] = True

    def committed(db: Any) -> None:
        if not db.in_nested_transaction():
            for candidate in db.info.pop("deleted_test_pdfs", set()):
                candidate.unlink(missing_ok=True)

    def rolled_back(db: Any) -> None:
        db.info.pop("deleted_test_pdfs", None)

    event.listen(sync, "after_commit", committed)
    event.listen(sync, "after_rollback", rolled_back)


async def confirm(
    message: Any, state: FSMContext, session: AsyncSession, bot: Bot, user: User
) -> None:
    """Recheck role/status and execute an explicitly confirmed destructive action."""
    data = await state.get_data()
    if await state.get_state() != CONFIRM_STATE:
        raise BusinessError(t("invalid"))
    key = data["confirm_action"]
    await admin_service.require(session, user.tg_id, ACTION_PERMISSIONS[key])
    test = await session.scalar(select(Test).where(Test.id == data["test_id"]).with_for_update())
    if test is None or test.status != data["confirm_status"] or key not in allowed(test):
        raise BusinessError(t("test_changed"))
    if key == "delete":
        if test.status != "draft" or test.scheduled_at is None:
            raise BusinessError(t("only_draft"))
        delete_pdf_after_commit(session, test.pdf_path)
        await session.delete(test)
        await session.flush()
        await state.set_state(None)
        await list_page(message, state, session, user)
    elif key == "close":
        await post_service.close(session, bot, test.id)
        await card(message, state, session, user, test.id)
    else:
        await post_service.results(session, bot, test.id)
        await card(message, state, session, user, test.id)


async def handle(
    message: Any, state: FSMContext, session: AsyncSession, bot: Bot, user: User
) -> bool:
    """Consume reply list selections, search input and preview confirmation states."""
    text = message.text or ""
    current = await state.get_state()
    data = await state.get_data()
    if current in (POST_INPUT, POST_CONFIRM):
        await post_answer(message, state, session, user)
        return True
    if current == EDIT_STATE:
        key = data["edit_action"]
        await admin_service.require(session, user.tg_id, "tests")
        test = await session.scalar(
            select(Test).where(Test.id == data["test_id"]).with_for_update()
        )
        if not test or test.status != data["edit_status"] or key not in allowed(test):
            raise BusinessError(t("test_changed"))
        await grading_service.change_key(session, test.id, text)
        await session.flush()
        await message.answer(t("saved"))
        await card(message, state, session, user, test.id)
        return True
    if current == AddTest.confirm.state:
        await admin_service.require(session, user.tg_id, "tests")
        keys = creation.preview_keys(data)
        choices = {t(key): key for key in keys if key != "cancel_input"}
        key = choices.get(text)
        if key is None:
            await message.answer(t("preview_actions"), reply_markup=build(keys))
            return True
        if key == "edit_post":
            await edit_post(message, state, session, user, preview=True)
            return True
        test_id = await creation.confirm(message, state, session, clear=False)
        if key != "schedule":
            await post_service.publish(
                session, bot, test_id, user.tg_id if key == "send_me" else None
            )
        await state.clear()
        await card(message, state, session, user, test_id)
        return True
    if current == CONFIRM_STATE:
        if text == t("yes"):
            await confirm(message, state, session, bot, user)
        elif text == t("no"):
            await card(message, state, session, user)
        else:
            await message.answer(
                t("input_controls"), reply_markup=build(["yes", "no", "back", "cancel_input"])
            )
        return True
    if current or data.get("nav_menu") != "test_list":
        return False
    if text in (t("previous_page"), t("next_page")):
        delta = 1 if text == t("next_page") else -1
        await list_page(message, state, session, user, page=data.get("test_page", 0) + delta)
        return True
    if text in data.get("test_choices", {}):
        await card(message, state, session, user, data["test_choices"][text])
        return True
    return False


async def edit_post(
    message: Any, state: FSMContext, session: AsyncSession, user: User, preview: bool = False
) -> None:
    """Open optional full-caption editing without adding creation steps."""
    await admin_service.require(session, user.tg_id, "tests")
    data = await state.get_data()
    if preview:
        draft = data["draft"]
        values = {key: value for key, value in draft.items() if key != "start_now"}
        for key in ("start_at", "end_at"):
            values[key] = datetime.fromisoformat(draft[key]) if draft.get(key) else None
        test = Test(**values)
    else:
        test = await session.get(Test, data["test_id"])
        if test is None or test.status != "draft" or test.scheduled_at is None:
            raise BusinessError(t("test_changed"))
    channel = await session.get(Channel, test.channel_id)
    text = post_service.caption(test, channel)
    await state.update_data(post_origin="preview" if preview else "card", post_candidate=None)
    await state.set_state(POST_INPUT)
    await message.answer(t("post_edit_prompt"), reply_markup=build(["back", "cancel_input"]))
    await message.answer(text, parse_mode=None)


async def return_post(message: Any, state: FSMContext, session: AsyncSession, user: User) -> None:
    """Return to the original preview or scheduled card, discarding unsaved text."""
    data = await state.get_data()
    await state.update_data(post_candidate=None)
    if data.get("post_origin") == "preview":
        await creation.show_preview(message, state, session)
    else:
        await card(message, state, session, user)


async def post_answer(message: Any, state: FSMContext, session: AsyncSession, user: User) -> None:
    """Preview and explicitly save caption text with live role/status checks."""
    await admin_service.require(session, user.tg_id, "tests")
    data = await state.get_data()
    test = None
    if data.get("post_origin") != "preview":
        test = await session.scalar(
            select(Test).where(Test.id == data["test_id"]).with_for_update()
        )
        if test is None or test.status != "draft" or test.scheduled_at is None:
            raise BusinessError(t("test_changed"))
    text = message.text or ""
    if await state.get_state() == POST_INPUT:
        if not text.strip() or len(text.encode("utf-16-le")) // 2 > 1024:
            raise BusinessError(t("post_edit_limit"))
        await state.update_data(post_candidate=text)
        await state.set_state(POST_CONFIRM)
        photo = data["draft"]["preview_file_id"] if test is None else test.preview_file_id
        await message.answer_photo(
            photo,
            caption=text,
            parse_mode=None,
            reply_markup=build(["save_post", "edit_post", "back", "cancel_input"]),
        )
        return
    if text == t("edit_post"):
        await state.set_state(POST_INPUT)
        await message.answer(t("post_edit_prompt"), reply_markup=build(["back", "cancel_input"]))
        return
    if text != t("save_post"):
        raise BusinessError(t("post_edit_confirm"))
    candidate = data["post_candidate"]
    if test is None:
        draft = data["draft"]
        draft["custom_caption"] = candidate
        await state.update_data(draft=draft)
    else:
        test.custom_caption = candidate
        await session.flush()
    await message.answer(t("post_edit_saved"))
    await return_post(message, state, session, user)
