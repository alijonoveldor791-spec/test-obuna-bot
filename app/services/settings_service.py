"""Database backed runtime settings."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Setting

DEFAULTS = {
    "protect_content": False,
    "referral_default": 0,
    "reminders": False,
    "show_key_after_close": False,
    "language": "uz",
}


async def get(session: AsyncSession, key: str):
    """Read current setting without stale process-local caches."""
    row = await session.get(Setting, key)
    return row.value["value"] if row else DEFAULTS.get(key)


async def set_value(session: AsyncSession, key: str, value: object) -> None:
    """Validate and update one known setting."""
    if key not in DEFAULTS:
        raise ValueError(key)
    default = DEFAULTS[key]
    if (
        type(value) is not type(default)
        or (key == "language" and value not in ("uz", "ru"))
        or (key == "referral_default" and not 0 <= value <= 1000)
    ):
        raise ValueError(key)
    await session.merge(Setting(key=key, value={"value": value}))
    await session.flush()
