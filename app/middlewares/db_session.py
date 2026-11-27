"""Per-update transactions serialized by Telegram user ID."""

from aiogram import BaseMiddleware
from redis.exceptions import LockNotOwnedError

from app.db.base import sessions
from app.db.models import User
from app.middlewares.private import is_private
from app.repositories.users import upsert
from app.services.referral_service import attribute


class DatabaseMiddleware(BaseMiddleware):
    """Inject a session and protect concurrent first-start updates."""

    def __init__(self, redis):
        self.redis = redis

    async def __call__(self, handler, event, data):
        if not is_private(event):
            return
        user = data.get("event_from_user") or getattr(event, "from_user", None)
        if user is None:
            return
        lock = self.redis.lock(f"update:{user.id}", timeout=120, blocking_timeout=2)
        if not await lock.acquire():
            return
        try:
            async with sessions.begin() as bootstrap:
                participant, is_new = await upsert(bootstrap, user)
                if is_new:
                    participant.lang = "uz"
                text = getattr(event, "text", None) or ""
                parts = text.split(maxsplit=1)
                if parts and parts[0].split("@")[0] == "/start" and len(parts) == 2:
                    payload = parts[1]
                    if payload.startswith("ref_") and payload[4:].isdigit():
                        await attribute(bootstrap, participant, int(payload[4:]), is_new)
                participant_id = participant.id
            async with sessions.begin() as session:
                data["session"] = session
                data["user"] = await session.get(User, participant_id)
                data["is_new"] = is_new
                return await handler(event, data)
        finally:
            try:
                await lock.release()
            except LockNotOwnedError:
                pass
