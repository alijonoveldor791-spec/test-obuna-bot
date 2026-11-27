"""Independent scheduler jobs and persistent bounded retries."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.scheduler import jobs
from app.scheduler.setup import create_scheduler


class Lock:
    """Serialize test invocations using an actual asyncio lock."""

    def __init__(self):
        self.lock = asyncio.Lock()

    async def __aenter__(self):
        await self.lock.acquire()

    async def __aexit__(self, *args):
        self.lock.release()


class MemoryRedis:
    """Share persisted state across job invocations and reconstructed schedulers."""

    def __init__(self):
        self.values = {}
        self.locks = {}

    def lock(self, key, **kwargs):
        return self.locks.setdefault(key, Lock())

    async def hgetall(self, key):
        return self.values.get(key, {})

    async def hset(self, key, mapping):
        self.values[key] = mapping

    async def delete(self, key):
        self.values.pop(key, None)


class Context:
    """Provide an async session stub."""

    async def __aenter__(self):
        return SimpleNamespace()

    async def __aexit__(self, *args):
        return False


async def test_retry_backoff_exhaustion_restart_and_notification(monkeypatch):
    redis = MemoryRedis()
    clock = [1000.0]
    monkeypatch.setattr(jobs.time, "time", lambda: clock[0])
    monkeypatch.setattr(jobs, "sessions", Context)
    notify = AsyncMock()
    monkeypatch.setattr(jobs, "notify_admins", notify)
    operation = AsyncMock(side_effect=RuntimeError("failure"))
    assert not await jobs.bounded_work(None, redis, "close:1", operation)
    assert not await jobs.bounded_work(None, redis, "close:1", operation)
    assert operation.await_count == 1
    clock[0] += 30
    await jobs.bounded_work(None, redis, "close:1", operation)
    clock[0] += 60
    await jobs.bounded_work(None, redis, "close:1", operation)
    # Reconstruction retains exhausted state and never repeats the admin alert.
    create_scheduler(None, redis)
    clock[0] += 1000
    await jobs.bounded_work(None, redis, "close:1", operation)
    assert operation.await_count == 3
    notify.assert_awaited_once()


async def test_success_clears_failures(monkeypatch):
    redis = MemoryRedis()
    redis.values["jobs:retry:batch"] = {"attempts": 1, "next_at": 0}
    assert await jobs.bounded_work(None, redis, "batch", AsyncMock())
    assert not redis.values


async def test_job_registration():
    scheduler = create_scheduler(None, None)
    registered = {job.id: job for job in scheduler.get_jobs()}
    assert set(registered) == {"tick", "broadcasts", "heartbeat", "subscriptions", "reminders"}
    assert registered["tick"].trigger.interval.total_seconds() == 30
    assert registered["broadcasts"].trigger.interval.total_seconds() == 1
    assert all(job.max_instances == 1 and job.coalesce for job in registered.values())


async def test_blocked_broadcast_does_not_block_heartbeat(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    entered, release = asyncio.Event(), asyncio.Event()

    async def long_batch():
        entered.set()
        await release.wait()

    redis = MemoryRedis()
    task = asyncio.create_task(jobs.bounded_work(None, redis, "broadcast:1", long_batch))
    await entered.wait()
    await asyncio.wait_for(jobs.heartbeat(None, redis), timeout=1)
    assert (tmp_path / "storage/heartbeat").exists()
    assert not task.done()
    release.set()
    await task
