"""Immediate participant ban enforcement."""

from aiogram import BaseMiddleware

from app.middlewares.private import is_private


class BanMiddleware(BaseMiddleware):
    """Silently stop banned participants."""

    async def __call__(self, handler, event, data):
        if not is_private(event):
            return
        if data["user"].is_banned:
            return
        return await handler(event, data)
