"""Reply navigation, permissions and parent-state behavior."""

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.db.models import Test
from app.services import application_service as app
from app.services import nav_service as nav
from app.services import test_creation_service as creation
from app.services.grading_service import GradingError, submit
from app.texts import t


async def press(d, db, key, user=None):
    """Send a real localized reply-button label through the dispatcher service."""
    d.message.text = t(key)
    await app.message(d.message, d.state, db, d.bot, d.redis, user or d.owner, False)


async def test_sections_back_cancel_and_unknown(db, domain):
    d = domain
    await press(d, db, "channels")
    assert (await d.state.get_data())["nav_menu"] == "channels"
    await press(d, db, "add_channel")
    assert await d.state.get_state() == nav.INPUT_STATE
    await press(d, db, "cancel_input")
    assert await d.state.get_state() is None
    assert (await d.state.get_data())["nav_menu"] == "channels"
    d.message.text = "unrecognized message"
    await app.message(d.message, d.state, db, d.bot, d.redis, d.owner, False)
    assert (await d.state.get_data())["nav_menu"] == "channels"
    await press(d, db, "back")
    assert (await d.state.get_data())["nav_menu"] == "admin"


async def test_forged_admin_button_and_live_role(db, domain):
    with pytest.raises(PermissionError):
        await press(domain, db, "channels", domain.user)
    with pytest.raises(PermissionError):
        await press(domain, db, "add_admin", domain.user)


async def test_user_mode_answer_prompt_and_cancel(db, domain):
    d = domain
    await press(d, db, "user_mode")
    await press(d, db, "submit_btn")
    assert await d.state.get_state() == nav.ANSWER_STATE
    await press(d, db, "cancel_input")
    assert (await d.state.get_data())["nav_menu"] == "user"
    d.message.text = "/start"
    await app.message(d.message, d.state, db, d.bot, d.redis, d.owner, False)
    assert (await d.state.get_data())["nav_menu"] == "admin"


async def test_settings_and_admin_input(db, domain):
    d = domain
    await press(d, db, "settings")
    await press(d, db, "reminders_btn")
    keyboard = d.message.answer.await_args.kwargs["reply_markup"]
    assert any(
        button.text == t("reminders_btn") + ": ✅" for row in keyboard.keyboard for button in row
    )
    await press(d, db, "channels")
    await press(d, db, "list_channels")
    assert await d.state.get_state() is None


async def test_closed_code_reuse_and_open_conflict(db, domain):
    d = domain
    d.test.status = "closed"
    await db.flush()
    with pytest.raises(GradingError, match="Bu test yopilgan"):
        await submit(db, d.user, "4829 ab")
    values = dict(
        code="4829",
        title="New",
        pdf_file_id="pdf",
        pdf_path="none",
        questions_count=2,
        answer_key={"1": "a", "2": "b"},
        created_by=1,
    )
    row = Test(**values, status="active", start_at=d.test.start_at)
    db.add(row)
    await db.flush()
    result, selected, _ = await submit(db, d.user, "4829 ab")
    assert selected.id == row.id and result.correct_count == 2
    with pytest.raises(IntegrityError):
        async with db.begin_nested():
            db.add(Test(**values, status="draft"))
            await db.flush()
    assert await db.scalar(select(Test.id).where(Test.id == row.id))


async def test_generated_code_and_invalid_database_codes(db, domain):
    assert await creation.available_code(db) != domain.test.code
    with pytest.raises(IntegrityError):
        async with db.begin_nested():
            db.add(
                Test(
                    code="12a4",
                    title="Bad",
                    pdf_file_id="p",
                    pdf_path="p",
                    questions_count=1,
                    answer_key={"1": "a"},
                    created_by=1,
                )
            )
            await db.flush()


async def test_creation_shortcuts_and_back(db, domain):
    """Manual and automatic code validation share the same creation flow."""
    from app.states.add_test import AddTest

    d = domain
    await d.state.set_state(AddTest.fields)
    await d.state.update_data(
        nav_menu="tests", draft={"title": "Sample"}, field_index=1, suggested="5830"
    )
    d.message.text = t("auto")
    await app.message(d.message, d.state, db, d.bot, d.redis, d.owner, False)
    draft = (await d.state.get_data())["draft"]
    assert draft["code"].isascii() and 1000 <= int(draft["code"]) <= 9999
    assert draft["code"] != d.test.code
    await press(d, db, "back")
    assert (await d.state.get_data())["field_index"] == 1
    await press(d, db, "cancel_input")
    assert await d.state.get_state() is None
    assert (await d.state.get_data())["nav_menu"] == "tests"
