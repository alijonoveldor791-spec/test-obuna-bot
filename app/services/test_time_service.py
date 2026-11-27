"""Timezone-aware test windows and directed date validation."""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from app.config import settings
from app.db.base import utcnow
from app.services.errors import BusinessError
from app.texts import t


def aware(value: datetime) -> datetime:
    """Restore UTC for database drivers returning naive timestamps."""
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def display(value: datetime) -> str:
    """Show a stored timestamp in the configured timezone."""
    return aware(value).astimezone(ZoneInfo(settings.tz)).strftime("%d.%m %H:%M")


def explicit(value: str) -> datetime:
    """Parse an unambiguous local wall-clock date."""
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M").replace(tzinfo=ZoneInfo(settings.tz))
    except ValueError as exc:
        raise BusinessError(t("date_format")) from exc


def beginning(value: str) -> tuple[datetime, bool]:
    """Resolve now, tomorrow morning, or a future local time."""
    now = utcnow()
    if value == t("start_now"):
        return now, True
    if value == t("start_tomorrow"):
        result = (now.astimezone(ZoneInfo(settings.tz)) + timedelta(days=1)).replace(
            hour=9, minute=0, second=0, microsecond=0
        )
    else:
        result = explicit(value)
    if result < now - timedelta(minutes=1):
        raise BusinessError(t("start_past"))
    return result, result <= now


def ending(value: str, start: datetime) -> datetime | None:
    """Resolve end shortcuts from the beginning and enforce ten minutes."""
    if value == t("unlimited_btn"):
        return None
    days = {t("day1"): 1, t("day3"): 3, t("day7"): 7}
    result = aware(start) + timedelta(days=days[value]) if value in days else explicit(value)
    if result < aware(start) + timedelta(minutes=10):
        raise BusinessError(t("end_too_early"))
    return result
