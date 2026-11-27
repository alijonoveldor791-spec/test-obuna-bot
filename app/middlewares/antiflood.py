"""Atomic Redis fixed-window rate limiter."""

from aiogram import BaseMiddleware

from app.middlewares.private import is_private

SCRIPT = "local n=redis.call('INCR',KEYS[1]); if n==1 then redis.call('PEXPIRE',KEYS[1],1000) end; return n"


async def allowed(redis, user_id: int) -> bool:
    """Allow up to three events per one-second window."""
    return int(await redis.eval(SCRIPT, 1, f"rate:{user_id}")) <= 3


class AntifloodMiddleware(BaseMiddleware):
    """Drop excess events before opening a database transaction."""

    def __init__(self, redis):
        self.redis = redis

    async def __call__(self, handler, event, data):
        if not is_private(event):
            return
        if not await allowed(self.redis, event.from_user.id):
            if getattr(event, "data", None) is not None:
                await event.answer()
            return
        return await handler(event, data)
