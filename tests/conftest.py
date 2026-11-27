"""Isolated async SQL fixtures."""

import os
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pymupdf
import pytest
import pytest_asyncio
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.db.models  # noqa: F401
from app.config import settings
from app.db.base import Base, utcnow
from app.db.models import Admin, Channel, Test, User
from tests.helpers import MemoryState, bot, message


@pytest_asyncio.fixture
async def db(tmp_path):
    """Provide a real transactional SQLite test database."""
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")

    @event.listens_for(engine.sync_engine, "connect")
    def foreign_keys(connection, record):
        connection.execute("PRAGMA foreign_keys=ON")

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory.begin() as session:
        yield session
    await engine.dispose()


@pytest_asyncio.fixture
async def domain(db, tmp_path, monkeypatch):
    """Provide a complete owner/channel/test graph with a generated PDF."""

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(settings, "bot_username", "sample_test_bot")
    path = tmp_path / "test.pdf"
    with pymupdf.open() as pdf:
        pdf.new_page().insert_text((20, 20), "Test")
        pdf.save(path)
    owner = User(tg_id=1, full_name="Owner")
    person = User(tg_id=2, full_name="Student")
    channel = Channel(
        tg_chat_id=-1001,
        title="Test channel",
        username="test_channel",
        is_required=True,
        is_main=True,
    )
    db.add_all([owner, person, channel, Admin(tg_id=1, role="owner")])
    await db.flush()
    test = Test(
        code="4829",
        title="Sample",
        description="Description",
        pdf_file_id="pdf_file",
        preview_file_id="preview_file",
        pdf_path=str(path),
        questions_count=2,
        answer_key={"1": "a", "2": "b"},
        created_by=1,
        status="active",
        start_at=utcnow(),
        channel_id=channel.id,
        max_attempts=1,
        prizes_count=1,
    )
    db.add(test)
    await db.flush()
    return SimpleNamespace(
        owner=owner,
        user=person,
        channel=channel,
        test=test,
        bot=bot(),
        state=MemoryState(),
        message=message(),
        redis=SimpleNamespace(get=AsyncMock(return_value=None), set=AsyncMock(return_value=True)),
    )


@pytest_asyncio.fixture
async def postgres_factory():
    """Create an isolated random PostgreSQL schema, never touch existing tables."""

    if os.getenv("TEST_INFRA") != "1":
        pytest.skip("Set TEST_INFRA=1 to enable PostgreSQL integration tests")
    schema = "bot_test_" + uuid.uuid4().hex
    admin = create_async_engine(settings.database_url)
    async with admin.begin() as connection:
        await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_async_engine(
        settings.database_url, connect_args={"server_settings": {"search_path": schema}}
    )
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        yield async_sessionmaker(engine, expire_on_commit=False)
    finally:
        await engine.dispose()
        async with admin.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        await admin.dispose()
