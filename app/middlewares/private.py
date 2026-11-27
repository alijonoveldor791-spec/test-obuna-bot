"""Private-chat boundary shared by update middleware."""

from typing import Any


def is_private(event: Any) -> bool:
    """Reject groups and inaccessible callback messages before persistence."""
    message = getattr(event, "message", None) or event
    chat = getattr(message, "chat", None)
    return chat is not None and chat.type == "private"
