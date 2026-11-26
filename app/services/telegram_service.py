"""Bounded retries for safe-to-retry Telegram failures."""

import asyncio

from aiogram.client.session.middlewares.base import BaseRequestMiddleware
from aiogram.exceptions import TelegramNetworkError, TelegramRetryAfter, TelegramServerError


class RetryMiddleware(BaseRequestMiddleware):
    """Retry transient read requests, avoiding duplicate outbound messages."""

    async def __call__(self, make_request, bot, method):
        for attempt in range(3):
            try:
                return await make_request(bot, method)
            except TelegramRetryAfter as exc:
                if attempt == 2 or exc.retry_after > 30:
                    raise
                await asyncio.sleep(exc.retry_after)
            except (TelegramNetworkError, TelegramServerError):
                if attempt == 2 or not method.__api_method__.startswith("get"):
                    raise
                await asyncio.sleep(0.5 * (attempt + 1))
