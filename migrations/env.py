"""Async Alembic runner."""

import asyncio

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

import app.db.models  # noqa: F401
from app.config import settings
from app.db.base import Base


def run(connection):
    """Apply migrations on supplied connection."""
    context.configure(connection=connection, target_metadata=Base.metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


async def online():
    """Connect asynchronously."""
    engine = create_async_engine(settings.database_url)
    async with engine.connect() as connection:
        await connection.run_sync(run)
    await engine.dispose()


if context.is_offline_mode():
    context.configure(url=settings.database_url, target_metadata=Base.metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    asyncio.run(online())
