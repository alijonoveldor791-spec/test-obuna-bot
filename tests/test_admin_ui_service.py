"""Administrator menus and edit workflows enforce roles."""

import pytest
from sqlalchemy import select

from app.db.models import Admin, Test
from app.services import admin_ui_service as ui
from app.services import grading_service
from tests.helpers import callback


async def test_menus_stats_exports(db, domain):
    d = domain
    await ui.home(d.message, db, d.owner)
    await ui.card(d.message, db, d.owner, d.test.id)
    await ui.list_tests(d.message, db, d.owner)
    for section in (
        "tests",
        "stats",
        "exports",
        "channels",
        "admins",
        "settings",
        "users",
        "broadcast",
    ):
        await ui.section(d.message, d.state, db, d.bot, d.owner, section)
    await grading_service.submit(db, d.user, "ab")
    for action in ("view", "ranking", "stats", "review"):
        await ui.test_action(
            callback("", d.message), d.state, db, d.bot, d.owner, action, d.test.id
        )
    await ui.export(d.message, db, d.owner, "users", 0)
    d.message.answer_document.assert_awaited_once()
    with pytest.raises(PermissionError):
        await ui.home(d.message, db, d.user)
    with pytest.raises(PermissionError):
        await ui.test_action(callback(), d.state, db, d.bot, d.user, "close", d.test.id)


async def test_user_settings_admin_edits(db, domain):
    d = domain
    for section, text in [
        ("settings", "protect_content true"),
        ("admins", "99 moderator"),
        ("admins", "99 admin"),
        ("admins", "del 99"),
        ("users", "2"),
        ("users", "ban 2"),
        ("users", "unban 2"),
    ]:
        await d.state.update_data(section=section)
        d.message.text = text
        await ui.input_value(d.message, d.state, db, d.bot, d.owner)
    assert await db.scalar(select(Admin.id).where(Admin.tg_id == 99)) is None
    assert not d.user.is_banned
    await d.state.update_data(section="users")
    d.message.text = "ban 1"
    with pytest.raises(ValueError):
        await ui.input_value(d.message, d.state, db, d.bot, d.owner)


async def test_lifecycle_and_changes(db, domain):
    d = domain
    cb = callback("", d.message)
    for action in ("pause", "resume"):
        await ui.test_action(cb, d.state, db, d.bot, d.owner, action, d.test.id)
    for action, value in [
        ("description", "Updated"),
        ("key", "1a, 2a"),
        ("deadline", "cheksiz"),
        ("schedule", "2030-01-01 12:00"),
    ]:
        await ui.test_action(cb, d.state, db, d.bot, d.owner, action, d.test.id)
        d.message.text = value
        await ui.input_value(d.message, d.state, db, d.bot, d.owner)
    assert d.test.answer_key == {"1": "a", "2": "a"} and d.test.description == "Updated"
    await ui.test_action(cb, d.state, db, d.bot, d.owner, "publish", d.test.id)
    await ui.test_action(cb, d.state, db, d.bot, d.owner, "send_me", d.test.id)
    await ui.test_action(cb, d.state, db, d.bot, d.owner, "close", d.test.id)
    await ui.test_action(cb, d.state, db, d.bot, d.owner, "winners", d.test.id)
    await ui.test_action(cb, d.state, db, d.bot, d.owner, "announce", d.test.id)
    assert d.test.results_published
    await ui.test_action(cb, d.state, db, d.bot, d.owner, "delete", d.test.id)
    await ui.test_action(cb, d.state, db, d.bot, d.owner, "delete_yes", d.test.id)
    assert await db.scalar(select(Test.id).where(Test.id == d.test.id)) is None
