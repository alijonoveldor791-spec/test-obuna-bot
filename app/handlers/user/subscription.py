"""Thin subscription-refresh adapter."""

from aiogram import Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User
from app.services.application_service import callback as process


async def handle(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    bot: Bot,
    redis: Redis,
    user: User,
) -> None:
    """Delegate subscription checks to the conversation service."""
    await process(callback, state, session, bot, redis, user)
