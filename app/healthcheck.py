"""Container health probe."""

import asyncio
import time
from pathlib import Path

from redis.asyncio import Redis
from sqlalchemy import text

from app.config import settings
from app.db.base import engine, sessions


async def check() -> None:
    """Check dependencies and the application's recent heartbeat."""
    redis = Redis.from_url(settings.redis_url)
    try:
        await redis.ping()
        async with sessions() as session:
            await session.execute(text("SELECT 1"))
        if time.time() - Path("storage/heartbeat").stat().st_mtime > 90:
            raise RuntimeError("Stale application heartbeat")
    finally:
        await redis.aclose()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(check())
