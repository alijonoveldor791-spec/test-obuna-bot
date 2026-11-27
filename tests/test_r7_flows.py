"""R7 directed settings, broadcast preview and cancellation regressions."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from app.db.models import Admin, Broadcast, Channel
from app.services import application_service as application
from app.services import broadcast_ui_service as broadcasts
from app.services import settings_ui_service as configuration
from app.services.admin_service import remove_channel, seed
from app.services.settings_service import get
from app.texts import t


async def send(d, db, text):
    """Exercise the public conversation dispatcher."""
    d.message.text = text
    await application.message(d.message, d.state, db, d.bot, d.redis, d.owner, False)


async def setting(d, db, key):
    """Start an owner settings operation."""
    await configuration.action(d.message, d.state, db, d.bot, d.owner, key)


async def test_owner_toggles_and_directed_admins(db, domain):
    d = domain
    for key, name in (
        ("protect_btn", "protect_content"),
        ("reminders_btn", "reminders"),
        ("key_btn", "show_key_after_close"),
    ):
        await setting(d, db, key)
        assert await get(db, name) is True
        keyboard = d.message.answer.await_args.kwargs["reply_markup"]
        assert any(t("setting_on") in b.text for row in keyboard.keyboard for b in row)
    await setting(d, db, "add_admin")
    with pytest.raises(ValueError):
        await send(d, db, "77 moderator")
    await send(d, db, "77")
    assert await d.state.get_state() == "Settings:role"
    await send(d, db, t("role_moderator"))
    row = await db.scalar(select(Admin).where(Admin.tg_id == 77))
    assert row.role == "moderator" and row.added_by == d.owner.tg_id
    await setting(d, db, "del_admin")
    choices = (await d.state.get_data())["settings_choices"]
    assert row.id in choices.values()
    owner = await db.scalar(select(Admin).where(Admin.tg_id == 1))
    assert owner.id not in choices.values()
    await send(d, db, next(iter(choices)))
    assert await db.get(Admin, row.id) is None
    await setting(d, db, "add_admin")
    with pytest.raises(ValueError):
        await send(d, db, "1")


async def test_revoked_owner_cannot_finish_input(db, domain):
    d = domain
    await setting(d, db, "add_admin")
    await send(d, db, "77")
    owner = await db.scalar(select(Admin).where(Admin.tg_id == 1))
    owner.role = "admin"
    await db.flush()
    with pytest.raises(PermissionError):
        await send(d, db, t("role_admin"))
    assert await db.scalar(select(Admin).where(Admin.tg_id == 77)) is None


async def test_channel_add_required_delete_main_and_no_grammar(db, domain):
    d = domain
    d.bot.get_chat = AsyncMock(
        return_value=SimpleNamespace(
            id=-1002, type="channel", title="Second", username="second", invite_link=None
        )
    )
    d.bot.get_me = AsyncMock(return_value=SimpleNamespace(id=10))
    d.bot.get_chat_member.return_value = SimpleNamespace(
        status="administrator", can_post_messages=True
    )
    await setting(d, db, "add_channel")
    with pytest.raises(ValueError):
        await send(d, db, "required 1 0")
    await send(d, db, "@second")
    channels = list((await db.scalars(select(Channel).order_by(Channel.id))).all())
    assert all(row.is_required for row in channels)
    assert channels[0].is_main and not channels[1].is_main
    await setting(d, db, "del_channel")
    choices = (await d.state.get_data())["settings_choices"]
    await send(d, db, next(label for label, id_ in choices.items() if id_ == channels[0].id))
    assert channels[1].is_main and channels[1].is_required
    await remove_channel(db, channels[1].id)
    assert not list((await db.scalars(select(Channel))).all())


@pytest.mark.parametrize("audience", ["all_btn", "participants_btn", "pending_btn"])
async def test_broadcast_preview_cancel_and_exact_photo_payload(db, domain, audience):
    d = domain
    await broadcasts.start(d.message, d.state, db, d.owner, audience)
    if audience != "all_btn":
        choices = (await d.state.get_data())["broadcast_tests"]
        with pytest.raises(ValueError):
            await send(d, db, str(d.test.id))
        await send(d, db, next(iter(choices)))
    d.message.photo = [SimpleNamespace(file_id="photo")]
    d.message.caption = "Announcement"
    await send(d, db, "")
    d.message.photo = None
    await send(d, db, t("broadcast_no_link"))
    row = await db.scalar(select(Broadcast))
    assert row.status == "draft"
    assert d.message.answer_photo.await_args.kwargs["caption"] == "Announcement"
    await send(d, db, t("cancel_input"))
    assert row.status == "cancelled"
    assert await d.state.get_data() == {"nav_menu": "broadcast"}
    assert await d.state.get_state() is None
    with pytest.raises(PermissionError):
        await broadcasts.start(d.message, d.state, db, d.user, "all_btn")


async def test_broadcast_url_limits_commands_and_live_authorization(db, domain):
    d = domain
    await broadcasts.start(d.message, d.state, db, d.owner, "all_btn")
    await send(d, db, "Hello")
    await send(d, db, t("broadcast_add_link"))
    await send(d, db, "Visit")
    for url in ("http://example.org", "https://user:pass@example.org", "https://exa mple.org"):
        with pytest.raises(ValueError):
            await send(d, db, url)
    await send(d, db, "https://example.org")
    row = await db.scalar(select(Broadcast))
    assert row.status == "draft"
    await send(d, db, "/start")
    assert row.status == "cancelled"
    await broadcasts.start(d.message, d.state, db, d.owner, "all_btn")
    with pytest.raises(ValueError):
        await send(d, db, "x" * 4097)
    await send(d, db, "Hello")
    await send(d, db, t("broadcast_no_link"))
    owner = await db.scalar(select(Admin).where(Admin.tg_id == 1))
    owner.role = "moderator"
    await db.flush()
    with pytest.raises(PermissionError):
        await send(d, db, t("broadcast_send"))
    rows = list((await db.scalars(select(Broadcast))).all())
    assert [row.status for row in rows] == ["cancelled", "draft"]


async def test_photo_link_total_limit_and_revoked_preview(db, domain):
    d = domain
    await broadcasts.start(d.message, d.state, db, d.owner, "all_btn")
    d.message.photo = [SimpleNamespace(file_id="photo")]
    d.message.caption = "x" * 1010
    await send(d, db, "")
    d.message.photo = None
    await send(d, db, t("broadcast_add_link"))
    await send(d, db, "Visit")
    with pytest.raises(ValueError):
        await send(d, db, "https://example.org")
    assert await db.scalar(select(Broadcast)) is None
    await send(d, db, t("cancel_input"))
    assert await d.state.get_data() == {"nav_menu": "broadcast"}


async def test_seed_makes_legacy_channels_required(db, domain):

    channel = await db.scalar(select(Channel))
    channel.is_required = False
    channel.is_main = False
    await seed(db)
    assert channel.is_required and channel.is_main
