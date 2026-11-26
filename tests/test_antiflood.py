"""Real Redis verifies the atomic three-event limiter."""

import asyncio
import os
import uuid

import pytest
from redis.asyncio import Redis

from app.config import settings
from app.middlewares.antiflood import allowed


@pytest.mark.skipif(
    os.getenv("TEST_INFRA") != "1",
    reason="TEST_INFRA=1 enables local Redis/PostgreSQL integration tests",
)
async def test_concurrent_limit():
    redis = Redis.from_url(settings.redis_url)
    user_id = int(uuid.uuid4().hex[:12], 16)
    try:
        results = await asyncio.gather(*(allowed(redis, user_id) for _ in range(20)))
        assert sum(results) == 3
        assert await redis.pttl(f"rate:{user_id}") > 0
    finally:
        await redis.delete(f"rate:{user_id}")
        await redis.aclose()
