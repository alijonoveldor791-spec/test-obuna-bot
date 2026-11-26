"""User-facing translations with Uzbek fallback."""

import json
from contextvars import ContextVar
from pathlib import Path

_LOCALES = {
    lang: json.loads(
        (Path(__file__).parent / "locales" / f"{lang}.json").read_text(encoding="utf-8")
    )
    for lang in ("uz", "ru")
}


current_language: ContextVar[str] = ContextVar("language", default="uz")


def t(message_key: str, lang: str | None = None, **values: object) -> str:
    """Format a localized string; missing translations fall back to Uzbek."""
    lang = lang or current_language.get()
    return str(_LOCALES.get(lang, {}).get(message_key, _LOCALES["uz"][message_key])).format(
        **values
    )


def headers(key: str) -> list[str]:
    """Return export column labels."""
    return _LOCALES["uz"][key]
