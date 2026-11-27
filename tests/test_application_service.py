"""Conversation routing connects user and admin features."""

import pytest
from aiogram.types import ReplyKeyboardMarkup
from sqlalchemy import select

from app.db.models import Admin
from app.keyboards.reply import ADMIN_KEYS, permission
from app.services import application_service as app
from app.services.admin_service import PERMISSIONS
from app.texts import t
from tests.helpers import callback


@pytest.mark.parametrize("role", ["owner", "admin", "moderator", None])
async def test_start_routes_by_live_role(db, domain, role):
    """Start resets stale actions and exposes only the current role's menu."""

    d = domain
    admin = await db.scalar(select(Admin).where(Admin.tg_id == d.owner.tg_id))
    if role:
        admin.role = role
    else:
        await db.delete(admin)
    await db.flush()
    await d.state.set_state("Settings:add_admin")
    await d.state.update_data(section="settings")
    d.message.text = "/start"
    await app.message(d.message, d.state, db, d.bot, d.redis, d.owner, False)
    assert await d.state.get_state() is None
    calls = d.message.answer.await_args_list
    keyboard = calls[0].kwargs["reply_markup"]
    assert isinstance(keyboard, ReplyKeyboardMarkup)
    assert keyboard.is_persistent
    labels = {button.text for row in keyboard.keyboard for button in row}
    if role:
        assert labels == {
            t(key)
            for key in ADMIN_KEYS
            if key == "user_mode" or permission(key) in PERMISSIONS[role]
        }
        d.bot.send_document.assert_not_awaited()
    else:
        assert labels == {
            t(key) for key in ("latest", "submit_btn", "results", "referral", "help_btn")
        }


@pytest.mark.parametrize(
    "command", ["/help", "/language ru", "/test", "/results", "/referral", "/cancel", "/unknown"]
)
async def test_removed_commands_do_not_execute(db, domain, command):
    """Retired commands redraw navigation without performing business actions."""
    d = domain
    d.message.text = command
    await app.message(d.message, d.state, db, d.bot, d.redis, d.owner, False)
    assert d.owner.lang == "uz"
    d.bot.send_document.assert_not_awaited()
    assert (await d.state.get_data())["nav_menu"] == "admin"


@pytest.mark.parametrize(
    "data",
    [
        "adm:stats",
        "new:start",
        "t:close:1",
        "exp:users:0",
        "bc:send:1",
        "list:active:0",
        "nav:pick:stats:1",
        "rank:1",
        "res:1",
        "unknown",
    ],
)
async def test_retired_callbacks_are_inert(db, domain, data):
    """Previously issued inline buttons cannot execute privileged work."""
    d = domain
    event = callback(data, d.message)
    await app.callback(event, d.state, db, d.bot, d.redis, d.owner)
    event.answer.assert_awaited_once()
    assert d.test.status == "active"
    d.message.answer.assert_not_awaited()
    d.bot.send_document.assert_not_awaited()
