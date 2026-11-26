"""Other administrator conversations."""

from aiogram.fsm.state import State, StatesGroup


class AdminInput(StatesGroup):
    """Generic service-validated admin input."""

    value = State()
