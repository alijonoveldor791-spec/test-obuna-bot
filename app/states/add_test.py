"""Test creation conversation states."""

from aiogram.fsm.state import State, StatesGroup


class AddTest(StatesGroup):
    """One question per test field, followed by preview."""

    pdf = State()
    fields = State()
    confirm = State()
