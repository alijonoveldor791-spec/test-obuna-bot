"""Polling and production webhook entry points."""

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.fsm.storage.redis import DefaultKeyBuilder, RedisStorage
from aiogram.types import ErrorEvent
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web
from redis.asyncio import Redis
from sqlalchemy import text

from app.config import settings
from app.db.base import engine, sessions
from app.handlers import build_router
from app.middlewares.antiflood import AntifloodMiddleware
from app.middlewares.ban_check import BanMiddleware
from app.middlewares.db_session import DatabaseMiddleware
from app.middlewares.user_upsert import UserMiddleware
from app.scheduler.setup import create_scheduler
from app.services.admin_service import channel_command, seed
from app.services.errors import BusinessError
from app.services.telegram_service import RetryMiddleware
from app.texts import t
from app.utils.logging import setup_logging


async def main() -> None:
    """Initialize dependencies, seed admins and run the selected transport."""
    setup_logging()
    if not settings.bot_token.get_secret_value():
        raise SystemExit("BOT_TOKEN ni .env faylida sozlang.")
    if settings.webhook_url and len(settings.webhook_secret.get_secret_value()) < 24:
        raise SystemExit("WEBHOOK_SECRET kamida 24 belgi bo'lishi kerak.")
    redis = Redis.from_url(settings.redis_url,socket_connect_timeout=5,socket_timeout=10,retry_on_timeout=True)
    await redis.ping()
    session = AiohttpSession(timeout=30)
    session.middleware(RetryMiddleware())
    bot = Bot(settings.bot_token.get_secret_value(), session=session)
    me = await bot.get_me()
    settings.bot_username = me.username
    dispatcher = Dispatcher(
        storage=RedisStorage(redis, key_builder=DefaultKeyBuilder(with_bot_id=True)), redis=redis
    )
    router = build_router()
    for observer in (router.message, router.callback_query):
        observer.outer_middleware(AntifloodMiddleware(redis))
        observer.outer_middleware(DatabaseMiddleware(redis))
        observer.outer_middleware(UserMiddleware())
        observer.outer_middleware(BanMiddleware())
    dispatcher.include_router(router)

    @dispatcher.errors()
    async def errors(event: ErrorEvent) -> bool:
        """Report actionable failures without disclosing credentials."""
        exc = event.exception
        update = event.update
        target = update.message or (
            update.callback_query.message if update.callback_query else None
        )
        if isinstance(exc, (ValueError, PermissionError, IndexError, KeyError)):
            message = (
                str(exc) if isinstance(exc, (BusinessError, PermissionError)) else t("invalid")
            )
            if target:
                await bot.send_message(target.chat.id, message, parse_mode=None)
        else:
            logging.getLogger(__name__).error(
                "Update failed", exc_info=(type(exc), exc, exc.__traceback__)
            )
            if target:
                await bot.send_message(target.chat.id, t("error"))
            for admin in settings.admins[:1]:
                try:
                    await bot.send_message(admin, t("admin_error"))
                except Exception:
                    pass
        return True

    async with sessions.begin() as db:
        await db.execute(text("SELECT 1"))
        await seed(db)
        if settings.main_channel_id:
            from sqlalchemy import select

            from app.db.models import Channel

            if not await db.scalar(
                select(Channel.id).where(Channel.tg_chat_id == settings.main_channel_id)
            ):
                await channel_command(db, bot, str(settings.main_channel_id))
    scheduler = create_scheduler(bot, redis)
    scheduler.start()
    try:
        if settings.webhook_url:
            app = web.Application()

            async def health(request):
                """Probe Redis and PostgreSQL for the orchestrator."""
                await redis.ping()
                async with sessions() as db:
                    await db.execute(text("SELECT 1"))
                return web.json_response({"status": "ok"})

            app.router.add_get("/health", health)
            SimpleRequestHandler(
                dispatcher, bot, secret_token=settings.webhook_secret.get_secret_value()
            ).register(app, path="/webhook")
            setup_application(app, dispatcher, bot=bot)
            await bot.set_webhook(
                settings.webhook_url + "/webhook",
                secret_token=settings.webhook_secret.get_secret_value(),
                allowed_updates=dispatcher.resolve_used_update_types(),
            )
            runner = web.AppRunner(app)
            await runner.setup()
            await web.TCPSite(runner, "0.0.0.0", 8080).start()
            try:
                await asyncio.Event().wait()
            finally:
                await runner.cleanup()
        else:
            await bot.delete_webhook(drop_pending_updates=False)
            await dispatcher.start_polling(bot, close_bot_session=False)
    finally:
        scheduler.shutdown(wait=False)
        await bot.session.close()
        await redis.aclose()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
