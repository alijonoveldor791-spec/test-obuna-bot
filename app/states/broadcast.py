"""Broadcast composer states."""

from aiogram.fsm.state import State, StatesGroup


class BroadcastInput(StatesGroup):
    """Audience, content and optional button."""

    audience = State()
    content = State()
    button = State()
    confirm = State()
