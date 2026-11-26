"""Per-update transactions serialized by Telegram user ID."""

from aiogram import BaseMiddleware
from redis.exceptions import LockNotOwnedError

from app.db.base import sessions


class DatabaseMiddleware(BaseMiddleware):
    """Inject a session and protect concurrent first-start updates."""

    def __init__(self, redis):
        self.redis = redis

    async def __call__(self, handler, event, data):
        user = data.get("event_from_user") or getattr(event, "from_user", None)
        if user is None:
            return
        lock = self.redis.lock(f"update:{user.id}", timeout=120, blocking_timeout=2)
        if not await lock.acquire():
            return
        try:
            async with sessions.begin() as session:
                data["session"] = session
                return await handler(event, data)
        finally:
            try:
                await lock.release()
            except LockNotOwnedError:
                pass
