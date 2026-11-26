"""Async database infrastructure."""

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


class Base(DeclarativeBase):
    """Shared SQLAlchemy metadata."""


def utcnow() -> datetime:
    """Return timezone aware UTC time."""
    return datetime.now(UTC)


connect_args = {"timeout":10,"command_timeout":60} if settings.database_url.startswith("postgresql") else {}
engine = create_async_engine(settings.database_url, pool_pre_ping=True,connect_args=connect_args)
sessions = async_sessionmaker(engine, expire_on_commit=False)
