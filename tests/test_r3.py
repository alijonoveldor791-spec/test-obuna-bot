"""Latest-test deep links, shared parsing and disk-independent publishing."""

from datetime import timedelta
from pathlib import Path

import pytest
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError

from app.db.models import Test
from app.services import application_service as app
from app.services.answer_parser import parse_answers, parse_key
from app.services.post_service import publish


@pytest.mark.parametrize("payload", ["test", "test_1", "test_999999", "ref_2"])
async def test_admin_deeplink_precedes_role(db, domain, payload):
    d = domain
    d.test.start_at -= timedelta(seconds=2)
    newest = Test(
        code="5830",
        title="Newest",
        pdf_file_id="new_pdf",
        pdf_path="missing",
        preview_file_id="photo",
        questions_count=2,
        answer_key={"1": "a", "2": "b"},
        status="active",
        start_at=d.test.start_at + timedelta(seconds=1),
        created_by=1,
    )
    db.add(newest)
    await db.flush()
    d.message.text = "/start " + payload
    await app.message(d.message, d.state, db, d.bot, d.redis, d.owner, False)
    assert d.bot.send_document.await_args.args[:2] == (d.owner.tg_id, "new_pdf")
    assert (await d.state.get_data())["nav_menu"] == "user"


async def test_no_active_test_and_subscription_resume(db, domain):
    d = domain
    d.test.status = "closed"
    d.message.text = "/start test_1"
    await app.message(d.message, d.state, db, d.bot, d.redis, d.owner, False)
    d.bot.send_document.assert_not_awaited()


async def test_publish_uses_saved_photo_and_generic_link(db, domain):
    d = domain
    Path(d.test.pdf_path).unlink()
    await publish(db, d.bot, d.test.id)
    call = d.bot.send_photo.await_args
    assert call.args[1] == "preview_file"
    assert call.kwargs["reply_markup"].inline_keyboard[0][0].url.endswith("?start=test")
    assert d.test.max_attempts == 1


@pytest.mark.parametrize("changes", [{"max_attempts": 2}, {"status": "paused"}])
async def test_legacy_lifecycle_values_rejected(db, domain, changes):
    """Database constraints reject removed lifecycle states and extra attempts."""

    with pytest.raises(IntegrityError):
        async with db.begin_nested():
            await db.execute(update(Test).where(Test.id == domain.test.id).values(**changes))


@pytest.mark.parametrize(
    "text",
    ["1a,2b,3c,4d", "1a 2b 3c 4d", "1-a,2-b,3-c,4-d", "ABCD", "1a\n2b\n3c\n4d", "1a,2b,3c,4d,"],
)
def test_shared_key_and_answers(text):
    assert parse_key(text, 4) == parse_answers(text, 4)


@pytest.mark.parametrize("text", ["1a,1b", "1a,2e", "1a", "0a,2b"])
def test_shared_invalid_formats(text):
    for parser in (parse_key, parse_answers):
        with pytest.raises(ValueError):
            parser(text, 2)
