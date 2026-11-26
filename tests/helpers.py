"""Realistic Telegram and FSM adapters for service integration tests."""

from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pymupdf


class MemoryState:
    """Mirror aiogram FSMContext operations with JSON-like data."""

    def __init__(self):
        self.state = None
        self.data = {}

    async def set_state(self, value):
        self.state = value.state if hasattr(value, "state") else value

    async def get_state(self):
        return self.state

    async def clear(self):
        self.state = None
        self.data = {}

    async def get_data(self):
        return deepcopy(self.data)

    async def update_data(self, **values):
        self.data.update(deepcopy(values))
        return await self.get_data()


def message(text="", tg_id=1):
    """Return a message double with async Telegram methods."""
    return SimpleNamespace(
        text=text,
        document=None,
        photo=None,
        caption=None,
        chat=SimpleNamespace(id=tg_id, type="private"),
        from_user=SimpleNamespace(id=tg_id, full_name="Owner", username="owner"),
        answer=AsyncMock(),
        answer_photo=AsyncMock(),
        answer_document=AsyncMock(),
    )


def callback(data="", msg=None):
    """Return a callback originating from a human user."""
    return SimpleNamespace(
        data=data, message=msg or message(), from_user=SimpleNamespace(id=1), answer=AsyncMock()
    )


def bot():
    """Return a Bot double with a valid photo publication response."""

    async def download(doc, destination):
        with pymupdf.open() as pdf:
            pdf.new_page().insert_text((20, 20), "Test")
            pdf.save(destination)

    result = SimpleNamespace(message_id=42, photo=[SimpleNamespace(file_id="preview_file")])
    return SimpleNamespace(
        send_message=AsyncMock(),
        send_photo=AsyncMock(return_value=result),
        send_document=AsyncMock(),
        download=AsyncMock(side_effect=download),
        get_chat_member=AsyncMock(return_value=SimpleNamespace(status="member")),
    )
