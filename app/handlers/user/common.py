"""Thin common Telegram adapter."""

from aiogram import Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User
from app.services.application_service import message as process


async def handle(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    bot: Bot,
    redis: Redis,
    user: User,
    is_new: bool,
) -> None:
    """Delegate validation and domain work to application services."""
    await process(message, state, session, bot, redis, user, is_new)
