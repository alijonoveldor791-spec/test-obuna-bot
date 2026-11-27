"""Runtime setting validation and fallback."""

import pytest

from app.services.settings_service import get, set_value
from app.texts import _LOCALES, t


async def test_settings(db):
    assert await get(db, "protect_content") is False
    await set_value(db, "protect_content", True)
    assert await get(db, "protect_content") is True
    for key, value in [
        ("unknown", True),
        ("referral_default", -1),
        ("protect_content", "yes"),
        ("language", "xx"),
    ]:
        with pytest.raises(ValueError):
            await set_value(db, key, value)


def test_translation():

    assert set(_LOCALES) == {"uz"}
    assert t("hello", "ru") == t("hello", "uz")
    assert t("answer_hint", "ru", code="1234", sample="1234 1?", questions=1) == t(
        "answer_hint", "uz", code="1234", sample="1234 1?", questions=1
    )
