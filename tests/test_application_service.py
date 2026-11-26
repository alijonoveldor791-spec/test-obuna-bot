"""Conversation routing connects user and admin features."""

import pytest

from app.services import application_service as app
from app.states.admin_misc import AdminInput
from tests.helpers import callback


@pytest.mark.parametrize("role", ["owner", "admin", "moderator", None])
async def test_start_routes_by_live_role(db, domain, role):
    """Start resets stale actions and exposes only the current role's menu."""
    from aiogram.types import ReplyKeyboardMarkup
    from sqlalchemy import select

    from app.db.models import Admin
    from app.services.admin_service import PERMISSIONS
    from app.texts import t

    d = domain
    admin = await db.scalar(select(Admin).where(Admin.tg_id == d.owner.tg_id))
    if role:
        admin.role = role
    else:
        await db.delete(admin)
    await db.flush()
    await d.state.set_state(AdminInput.value)
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
        from app.keyboards.reply import ADMIN_KEYS, permission

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


async def test_user_and_admin_commands(db, domain):
    d = domain
    for text in (
        "/start",
        "/help",
        "/language ru",
        "/test",
        "/results",
        "/referral",
        "/cancel",
        "/admin",
        "/unknown",
    ):
        d.message.text = text
        await app.message(d.message, d.state, db, d.bot, d.redis, d.owner, False)
    assert d.owner.lang == "ru"
    for data in (
        "adm:stats",
        "adm:exports",
        "list:active:0",
        f"t:view:{d.test.id}",
        "exp:users:0",
        "ref:progress",
        "sub:check",
        "new:start",
        "new:cancel",
    ):
        await app.callback(callback(data, d.message), d.state, db, d.bot, d.redis, d.owner)
    d.message.text = "/language xx"
    with pytest.raises(ValueError):
        await app.message(d.message, d.state, db, d.bot, d.redis, d.owner, False)
    with pytest.raises(ValueError):
        await app.callback(callback("unknown"), d.state, db, d.bot, d.redis, d.owner)


async def test_admin_input_dispatch(db, domain):
    d = domain
    await d.state.set_state(AdminInput.value)
    await d.state.update_data(section="settings")
    d.message.text = "reminders true"
    await app.message(d.message, d.state, db, d.bot, d.redis, d.owner, False)
    assert await d.state.get_state() is None
    d.message.text = "4829 ab"
    await app.message(d.message, d.state, db, d.bot, d.redis, d.owner, False)
