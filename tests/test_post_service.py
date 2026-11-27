"""Publication and reviewed result announcements."""

import pytest

from app.services.grading_service import submit
from app.services.post_service import caption, close, publish, results


async def test_publish_and_results(db, domain, monkeypatch):
    monkeypatch.setattr("app.services.post_service.settings.admin_ids", "1")
    test = domain.test
    test.description = "emoji " * 1000
    text = caption(test, domain.channel)
    assert len(text.encode("utf-16-le")) // 2 <= 1024
    assert test.code in text and "https://t.me/" in text
    test.status = "draft"
    test.channel_post_id = None
    await publish(db, domain.bot, test.id)
    assert test.channel_post_id == 42 and test.preview_file_id == "preview_file"
    await publish(db, domain.bot, test.id, 1)
    row, _, _ = await submit(db, domain.user, "ab")
    await close(db, domain.bot, test.id)
    assert test.status == "closed"
    await close(db, domain.bot, test.id)
    test.show_key_after_close = True
    await results(db, domain.bot, test.id)
    assert test.results_published and row.rank == 1
    assert domain.bot.send_message.await_count == 2
    with pytest.raises(ValueError):
        await results(db, domain.bot, test.id)
    with pytest.raises(ValueError):
        await publish(db, domain.bot, test.id)


async def test_no_channel(db, domain):
    test = domain.test
    test.channel_id = None
    await db.flush()
    with pytest.raises(ValueError):
        await publish(db, domain.bot, test.id)
    assert caption(test, None)
