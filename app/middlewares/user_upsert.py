"""Persist Telegram users before domain handlers."""

from aiogram import BaseMiddleware

from app.middlewares.private import is_private
from app.repositories.users import upsert


class UserMiddleware(BaseMiddleware):
    """Inject user and first-start flag."""

    async def __call__(self, handler, event, data):
        if not is_private(event):
            return
        if "user" not in data:
            data["user"], data["is_new"] = await upsert(data["session"], event.from_user)
        data["user"].lang = "uz"
        return await handler(event, data)
