"""Register only private messages and subscription refresh callbacks."""

from aiogram import F, Router
from aiogram.filters import Command, CommandStart

from app.filters.is_private import IsPrivate
from app.handlers.user import common, subscription


def build_router() -> Router:
    """Wire two commands and declared reply labels to thin adapters."""
    router = Router()
    router.message.filter(IsPrivate())
    router.callback_query.filter(IsPrivate())
    router.message.register(common.handle, CommandStart())
    router.message.register(common.handle, Command("admin"))
    router.message.register(common.handle)
    router.callback_query.register(subscription.handle, F.data == "sub:check")
    return router
