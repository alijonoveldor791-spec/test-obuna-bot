"""Immediate participant ban enforcement."""

from aiogram import BaseMiddleware


class BanMiddleware(BaseMiddleware):
    """Silently stop banned participants."""

    async def __call__(self, handler, event, data):
        if data["user"].is_banned:
            return
        return await handler(event, data)
