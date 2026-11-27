"""R4 declarative navigation, access boundaries and Uzbek-only rendering."""

from types import SimpleNamespace

import pytest
from aiogram.types import ReplyKeyboardMarkup
from sqlalchemy import select

from app.db.models import Admin
from app.handlers import build_router
from app.keyboards.reply import menu_keyboard
from app.menus import MENUS, Menu, permissions_for
from app.services import application_service as app
from app.services import nav_service as nav
from app.services.admin_service import PERMISSIONS
from app.texts import t


@pytest.mark.parametrize("role", ["owner", "admin", "moderator", None])
async def test_all_declared_access_boundaries(db, domain, role):
    """A forged button is checked by ancestors as well as the current row."""
    d = domain
    admin = await db.scalar(select(Admin).where(Admin.tg_id == 1))
    if role:
        admin.role = role
    else:
        await db.delete(admin)
    await db.flush()
    for key in MENUS:
        if key in ("admin", "user") or not MENUS[key].visible:
            continue
        permitted = permissions_for(key) <= PERMISSIONS.get(role, set())
        d.message.text = t(MENUS[key].title)
        await d.state.clear()
        if not permitted:
            with pytest.raises(PermissionError):
                await nav.handle(d.message, d.state, db, d.bot, d.redis, d.owner)
        else:
            assert await nav.handle(d.message, d.state, db, d.bot, d.redis, d.owner)


@pytest.mark.parametrize(
    "role,expected",
    [
        (
            "owner",
            (
                "new_test",
                "tests",
                "stats",
                "exports",
                "broadcast",
                "users",
                "settings",
                "user_mode",
            ),
        ),
        ("admin", ("new_test", "tests", "stats", "exports", "broadcast", "users", "user_mode")),
        ("moderator", ("tests", "stats", "exports", "user_mode")),
    ],
)
def test_main_menu_order(role, expected):
    keyboard = menu_keyboard("admin", role)
    assert isinstance(keyboard, ReplyKeyboardMarkup)
    assert keyboard.resize_keyboard and keyboard.is_persistent
    assert [button.text for row in keyboard.keyboard for button in row] == [
        t(key) for key in expected
    ]


async def test_nested_parent_navigation_and_state_clear(db, domain):
    d = domain
    for key in ("settings", "channels"):
        d.message.text = t(key)
        await app.message(d.message, d.state, db, d.bot, d.redis, d.owner, False)
    d.message.text = t("back")
    await app.message(d.message, d.state, db, d.bot, d.redis, d.owner, False)
    assert (await d.state.get_data())["nav_menu"] == "settings"
    await d.state.set_state("Future:input")
    await d.state.update_data(draft={"secret": "temporary"})
    d.message.text = t("cancel_input")
    await app.message(d.message, d.state, db, d.bot, d.redis, d.owner, False)
    assert await d.state.get_state() is None
    assert await d.state.get_data() == {"nav_menu": "settings"}
    d.message.text = t("home")
    await app.message(d.message, d.state, db, d.bot, d.redis, d.owner, False)
    assert (await d.state.get_data())["nav_menu"] == "admin"


async def test_new_row_needs_no_router_or_dispatch_changes(db, domain, monkeypatch):
    """One menu row inherits its parent's access and shared dispatch behavior."""
    monkeypatch.setitem(MENUS, "extra", Menu("nav_prompt", "settings"))
    labels = [button.text for row in menu_keyboard("settings", "owner").keyboard for button in row]
    assert t("nav_prompt") in labels
    d = domain
    d.message.text = t("nav_prompt")
    await nav.handle(d.message, d.state, db, d.bot, d.redis, d.owner)
    assert (await d.state.get_data())["nav_menu"] == "extra"
    with pytest.raises(PermissionError):
        await nav.handle(d.message, d.state, db, d.bot, d.redis, d.user)


async def test_unknown_text_keeps_current_menu(db, domain):
    d = domain
    await nav.show(d.message, d.state, db, d.owner, "settings")
    d.message.text = "nonsense"
    await app.message(d.message, d.state, db, d.bot, d.redis, d.owner, False)
    assert (await d.state.get_data())["nav_menu"] == "settings"


async def test_old_language_value_does_not_change_ui(db, domain):
    d = domain
    d.owner.lang = "ru"
    d.message.text = "/start"
    await app.message(d.message, d.state, db, d.bot, d.redis, d.owner, False)
    assert d.owner.lang == "uz"
    assert d.message.answer.await_args.args[0] == t("admin_menu", "uz")


async def test_retired_commands_cannot_cancel_or_mutate_input(db, domain):
    d = domain
    await d.state.set_state(nav.ANSWER_STATE)
    await d.state.update_data(nav_menu="user", draft={"saved": True})
    for command in ("/cancel", "/language ru", "/test"):
        d.message.text = command
        await app.message(d.message, d.state, db, d.bot, d.redis, d.owner, False)
        assert await d.state.get_state() == nav.ANSWER_STATE
        assert (await d.state.get_data())["draft"] == {"saved": True}
        assert d.owner.lang == "uz"
    d.bot.send_document.assert_not_awaited()


async def test_role_revocation_hides_previous_section(db, domain):
    d = domain
    await nav.show(d.message, d.state, db, d.owner, "channels")
    admin = await db.scalar(select(Admin).where(Admin.tg_id == 1))
    admin.role = "moderator"
    await db.flush()
    d.message.text = t("add_channel")
    with pytest.raises(PermissionError):
        await nav.handle(d.message, d.state, db, d.bot, d.redis, d.owner)
    d.message.text = t("home")
    await nav.handle(d.message, d.state, db, d.bot, d.redis, d.owner)
    labels = [
        button.text
        for row in d.message.answer.await_args.kwargs["reply_markup"].keyboard
        for button in row
    ]
    assert t("settings") not in labels and t("tests") in labels


async def test_router_only_accepts_subscription_callback():
    """Actual aiogram filters reject retired admin callback payloads."""
    router = build_router()
    assert len(router.callback_query.handlers) == 1
    handler = router.callback_query.handlers[0]
    for payload, expected in (("sub:check", True), ("t:close:1", False), ("new:start", False)):
        event = SimpleNamespace(data=payload)
        accepted = all([await filter_.call(event) for filter_ in handler.filters])
        assert accepted is expected
