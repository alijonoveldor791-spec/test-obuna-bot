"""Private-chat filters."""

from aiogram.filters import Filter


class IsPrivate(Filter):
    """Reject group and channel interactions."""

    async def __call__(self, event) -> bool:
        chat = getattr(event, "chat", None) or getattr(
            getattr(event, "message", None), "chat", None
        )
        return bool(chat and chat.type == "private")
