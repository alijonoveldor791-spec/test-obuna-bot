"""User-facing translations with Uzbek fallback."""

import json
from pathlib import Path

_LOCALES = {
    "uz": json.loads((Path(__file__).parent / "locales" / "uz.json").read_text(encoding="utf-8"))
}


def t(message_key: str, lang: str | None = None, **values: object) -> str:
    """Format a localized string; missing translations fall back to Uzbek."""
    return str(_LOCALES["uz"][message_key]).format(**values)


def headers(key: str) -> list[str]:
    """Return export column labels."""
    return _LOCALES["uz"][key]
