"""Broadcast audiences, composition, cancellation and delivery failures."""

from unittest.mock import AsyncMock

import pytest
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
from aiogram.methods import SendMessage
from sqlalchemy import select

from app.db.models import AccessLog, Broadcast
from app.services import broadcast_ui_service as ui
from app.services.broadcast_service import audience_query, run_batch, send_one
from app.texts import t


async def test_composer(db, domain):
    d = domain

    await ui.start(d.message, d.state, db, d.owner, "pending_btn")
    d.message.text = next(iter((await d.state.get_data())["broadcast_tests"]))
    await ui.handle(d.message, d.state, db, d.owner)
    for text in ("Test announcement", t("broadcast_add_link"), "Visit", "https://example.org"):
        d.message.text = text
        await ui.handle(d.message, d.state, db, d.owner)
    row = await db.scalar(select(Broadcast))
    assert row.status == "draft" and row.total == 0
    assert d.message.answer.call_args_list[-2].args[0] == ui.outgoing(
        (await d.state.get_data())["broadcast"]
    )
    d.message.text = t("broadcast_send")
    await ui.handle(d.message, d.state, db, d.owner)
    assert row.status == "running"
    d.message.text = t("broadcast_stop")
    await ui.handle(d.message, d.state, db, d.owner)
    assert row.status == "cancelled"


async def test_send_and_failures(db, domain, monkeypatch):
    d = domain
    row = Broadcast(
        text="Hello", audience="all", button_text="Link", button_url="https://example.org"
    )
    db.add(row)
    await db.flush()
    assert await send_one(d.bot, d.user, row)
    row.media_file_id = "photo"
    assert await send_one(d.bot, d.user, row)
    row.media_file_id = None
    d.bot.send_message.side_effect = TelegramForbiddenError(
        method=SendMessage(chat_id=2, text="hi"), message="blocked"
    )
    assert not await send_one(d.bot, d.user, row)
    assert d.user.is_blocked
    d.user.is_blocked = False
    d.bot.send_message.side_effect = [
        TelegramRetryAfter(method=SendMessage(chat_id=2, text="hi"), message="wait", retry_after=1),
        None,
    ]
    monkeypatch.setattr("app.services.broadcast_service.asyncio.sleep", AsyncMock())
    assert await send_one(d.bot, d.user, row)


async def test_audiences_and_batch(db, domain, monkeypatch):
    d = domain
    row = Broadcast(text="Hello", audience="pending", test_id=d.test.id, status="running")
    db.add_all([row, AccessLog(test_id=d.test.id, user_id=d.user.id)])
    await db.flush()
    assert list((await db.scalars(audience_query(row))).all()) == [d.user]
    row.audience = "participants"
    assert not list((await db.scalars(audience_query(row))).all())
    row.audience = "left"
    assert not list((await db.scalars(audience_query(row))).all())
    row.audience = "all"

    class Factory:
        def begin(self):
            class Context:
                async def __aenter__(self):
                    return db

                async def __aexit__(self, *args):
                    await db.flush()

            return Context()

    monkeypatch.setattr("app.services.broadcast_service.sessions", Factory())
    monkeypatch.setattr("app.services.broadcast_service.asyncio.sleep", AsyncMock())
    await run_batch(d.bot, row.id)
    assert row.status == "done" and row.sent == 2
    await run_batch(d.bot, row.id)
    assert row.sent == 2


async def test_invalid_composer(db, domain):
    d = domain
    await ui.start(d.message, d.state, db, d.owner, "all_btn")
    d.message.text = ""
    with pytest.raises(ValueError):
        await ui.handle(d.message, d.state, db, d.owner)
