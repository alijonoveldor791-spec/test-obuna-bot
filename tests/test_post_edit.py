"""Optional caption editing preserves creation steps and scheduled publication."""

from datetime import timedelta
from importlib import import_module
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, select, text

from app.db.base import utcnow
from app.db.models import Admin, Test
from app.services import test_manage_service as management
from app.services.post_service import caption, publish
from app.states.add_test import AddTest
from app.texts import t
from tests.test_r11 import preview, send


async def test_preview_edit_save_publish(db, domain):
    d = domain
    await preview(d, db)
    await send(d, db, t("edit_post"))
    assert await d.state.get_state() == management.POST_INPUT
    original = d.message.answer.await_args.args[0]
    text = "🧪 Kimyo testi!\n" + original + "\n🔥 Omad tilaymiz!"
    await send(d, db, text)
    assert d.message.answer_photo.await_args.kwargs["caption"] == text
    assert not (await d.state.get_data())["draft"].get("custom_caption")
    await send(d, db, t("save_post"))
    assert await d.state.get_state() == AddTest.confirm.state
    assert (await d.state.get_data())["draft"]["custom_caption"] == text
    await send(d, db, t("publish"))
    assert d.bot.send_photo.await_args.kwargs["caption"] == text
    row = await db.scalar(select(Test).where(Test.id != d.test.id))
    assert row.custom_caption == text and row.questions_count == 3


async def test_scheduled_edit_cancel_then_save_and_publish(db, domain):
    d = domain
    d.test.status = "draft"
    d.test.start_at = utcnow() + timedelta(days=1)
    d.test.scheduled_at = d.test.start_at
    await db.flush()
    await management.card(d.message, d.state, db, d.owner, d.test.id)
    await send(d, db, t("edit_post"))
    await send(d, db, "❌ Unsaved")
    await send(d, db, t("cancel_input"))
    assert d.test.custom_caption is None
    await send(d, db, t("edit_post"))
    await send(d, db, "🧪 Rejalashtirilgan test\nIzoh va emojilar ✅")
    await send(d, db, t("save_post"))
    await db.refresh(d.test)
    assert d.test.custom_caption.endswith("✅")
    assert d.test.scheduled_at and d.test.status == "draft"
    d.test.start_at = utcnow() - timedelta(seconds=1)
    await db.flush()
    await publish(db, d.bot, d.test.id)
    assert d.bot.send_photo.await_args.kwargs["caption"] == d.test.custom_caption


async def test_limits_back_and_preview_kept(db, domain):
    d = domain
    await preview(d, db)
    await send(d, db, t("edit_post"))
    for value in (" ", "a" * 1025, "🔥" * 513):
        with pytest.raises(ValueError):
            await send(d, db, value)
    await send(d, db, "🔥" * 512)
    await send(d, db, t("back"))
    assert await d.state.get_state() == AddTest.confirm.state
    assert not (await d.state.get_data())["draft"].get("custom_caption")
    await send(d, db, t("edit_post"))
    await send(d, db, "First")
    await send(d, db, t("edit_post"))
    await send(d, db, "Second ✅")
    await send(d, db, t("save_post"))
    assert (await d.state.get_data())["draft"]["custom_caption"] == "Second ✅"


async def test_live_role_and_status_checks(db, domain):
    d = domain
    d.test.status = "draft"
    d.test.scheduled_at = utcnow() + timedelta(days=1)
    await db.flush()
    await management.card(d.message, d.state, db, d.owner, d.test.id)
    await send(d, db, t("edit_post"))
    await send(d, db, "New caption")
    d.test.status = "active"
    await db.flush()
    with pytest.raises(ValueError):
        await send(d, db, t("save_post"))
    assert d.test.custom_caption is None
    d.test.status = "draft"
    admin = await db.scalar(select(Admin).where(Admin.tg_id == d.owner.tg_id))
    admin.role = "moderator"
    await db.flush()
    with pytest.raises(PermissionError):
        await send(d, db, t("save_post"))
    with pytest.raises(PermissionError):
        await management.edit_post(d.message, d.state, db, d.user)


async def test_existing_caption_fallback(db, domain):
    assert domain.test.code in caption(domain.test, domain.channel)
    assert domain.test.custom_caption is None


def test_caption_migration_preserves_existing_row(monkeypatch):
    migration = import_module("migrations.versions.d460_custom_caption")
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE tests (id INTEGER PRIMARY KEY, title TEXT)"))
        connection.execute(text("INSERT INTO tests VALUES (1, 'Existing')"))
        monkeypatch.setattr(migration, "op", Operations(MigrationContext.configure(connection)))
        migration.upgrade()
        assert connection.execute(text("SELECT title, custom_caption FROM tests")).one() == (
            "Existing",
            None,
        )
        migration.downgrade()
        assert [column["name"] for column in inspect(connection).get_columns("tests")] == [
            "id",
            "title",
        ]
    engine.dispose()


async def test_command_discards_preview_edit_pdf(db, domain):
    d = domain
    await preview(d, db)
    from_path = Path((await d.state.get_data())["draft"]["pdf_path"])
    await send(d, db, t("edit_post"))
    await send(d, db, "/start")
    assert not from_path.exists()
    assert await d.state.get_state() is None
