"""Complete PDF intake, metadata validation, preview and persistence."""

from datetime import timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.db.base import utcnow
from app.db.models import Test
from app.services import test_creation_service as create
from app.states.add_test import AddTest
from tests.helpers import callback


async def test_full_draft(db, domain):
    d = domain
    await create.start(d.message, d.state)
    assert await d.state.get_state() == AddTest.pdf.state
    d.message.document = SimpleNamespace(
        mime_type="application/pdf", file_size=100, file_id="test_pdf"
    )
    await create.receive_pdf(d.message, d.state, db, d.bot)
    values = [
        "New test",
        "5830",
        "Short description",
        "2",
        "1a, 2b",
        (utcnow() + timedelta(days=1)).strftime("%Y-%m-%d %H:%M"),
        "1",
        __import__("app.texts", fromlist=["t"]).t("disable"),
        "1",
        str(d.channel.id),
    ]
    for value in values:
        d.message.text = value
        await create.field_value(d.message, d.state, db)
    assert await d.state.get_state() == AddTest.confirm.state
    d.message.answer_photo.assert_awaited_once()
    test_id = await create.confirm(callback("new:confirm"), d.state, db)
    row = await db.get(Test, test_id)
    assert row.status == "draft" and row.answer_key == {"1": "a", "2": "b"} and row.created_by == 1
    assert await d.state.get_state() is None
    with pytest.raises(ValueError):
        await create.confirm(callback("new:confirm"), d.state, db)


async def test_bad_pdf_and_fields(db, domain):
    d = domain
    await create.start(d.message, d.state)
    with pytest.raises(ValueError):
        await create.receive_pdf(d.message, d.state, db, d.bot)
    d.message.document = SimpleNamespace(mime_type="application/pdf", file_size=21 * 1024 * 1024)
    with pytest.raises(ValueError):
        await create.receive_pdf(d.message, d.state, db, d.bot)
    await d.state.update_data(draft={}, field_index=1, suggested="6831")
    for value in ["4829", "letters", "A" + "1" * 40]:
        d.message.text = value
        with pytest.raises(ValueError):
            await create.field_value(d.message, d.state, db)
    await d.state.update_data(field_index=0)
    d.message.text = "x" * 201
    with pytest.raises(ValueError):
        await create.field_value(d.message, d.state, db)
    assert await db.scalar(select(Test.id).where(Test.code == "5830")) is None


def test_dates():
    assert create.parse_date("cheksiz") is None
    with pytest.raises(ValueError):
        create.parse_date("2020-01-01 00:00")
    with pytest.raises(ValueError):
        create.parse_date("bad")
