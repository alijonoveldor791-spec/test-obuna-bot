"""Telegram deep links."""


def link(username: str, payload: str) -> str:
    """Build a Telegram bot start link."""
    return f"https://t.me/{username.lstrip('@')}?start={payload}"
