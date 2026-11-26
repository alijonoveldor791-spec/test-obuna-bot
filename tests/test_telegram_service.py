"""Read retries and outgoing message duplicate protection."""

from unittest.mock import AsyncMock

import pytest
from aiogram.exceptions import TelegramNetworkError, TelegramRetryAfter
from aiogram.methods import GetMe, SendMessage

from app.services.telegram_service import RetryMiddleware


async def test_read_retry(monkeypatch):
    monkeypatch.setattr("app.services.telegram_service.asyncio.sleep", AsyncMock())
    method = GetMe()
    request = AsyncMock(side_effect=[TelegramNetworkError(method=method, message="timeout"), "ok"])
    assert await RetryMiddleware()(request, object(), method) == "ok"
    assert request.await_count == 2


async def test_send_not_retried(monkeypatch):
    monkeypatch.setattr("app.services.telegram_service.asyncio.sleep", AsyncMock())
    method = SendMessage(chat_id=1, text="hello")
    request = AsyncMock(side_effect=TelegramNetworkError(method=method, message="timeout"))
    with pytest.raises(TelegramNetworkError):
        await RetryMiddleware()(request, object(), method)
    assert request.await_count == 1
    request = AsyncMock(
        side_effect=[TelegramRetryAfter(method=method, message="wait", retry_after=1), "ok"]
    )
    assert await RetryMiddleware()(request, object(), method) == "ok"
