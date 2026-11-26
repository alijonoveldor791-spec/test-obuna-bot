"""Persist Telegram users before domain handlers."""

from aiogram import BaseMiddleware

from app.repositories.users import upsert
from app.services.settings_service import get
from app.texts import current_language


class UserMiddleware(BaseMiddleware):
    """Inject user and first-start flag."""

    async def __call__(self, handler, event, data):
        data["user"], data["is_new"] = await upsert(data["session"], event.from_user)
        if data["is_new"]:
            data["user"].lang = await get(data["session"], "language")
        token = current_language.set(data["user"].lang)
        try:
            return await handler(event, data)
        finally:
            current_language.reset(token)
