"""Subscription continuation, download logging, grading and history."""

from types import SimpleNamespace

from sqlalchemy import func, select

from app.db.models import AccessLog
from app.services import user_service as users
from tests.helpers import callback, message


async def test_gate_resume_and_results(db, domain):
    d = domain
    d.message = message("/start test_" + str(d.test.id), tg_id=2)
    d.bot.get_chat_member.return_value = SimpleNamespace(status="left")
    await users.start(d.message, d.state, db, d.bot, d.redis, d.user, False)
    d.bot.send_document.assert_not_awaited()
    assert (await d.state.get_data())["pending_action"] == "test"
    d.bot.get_chat_member.return_value = SimpleNamespace(status="member")
    await users.resume(callback("sub:check", d.message), d.state, db, d.bot, d.redis, d.user)
    d.bot.send_document.assert_awaited_once()
    await users.send_test(d.message, d.state, db, d.bot, d.redis, d.user)
    assert await db.scalar(select(func.count()).select_from(AccessLog)) == 1
    d.message.text = "ab"
    await users.answers(d.message, d.state, db, d.bot, d.redis, d.user)
    await users.my_results(d.message, db, d.user)
    await users.referral(d.message, db, d.user)
    d.test.status = "closed"
    await users.send_test(d.message, d.state, db, d.bot, d.redis, d.user)


async def test_pending_answers(db, domain):
    d = domain
    msg = message("4829 ab", tg_id=2)
    d.bot.get_chat_member.return_value = SimpleNamespace(status="left")
    await users.answers(msg, d.state, db, d.bot, d.redis, d.user)
    assert (await d.state.get_data())["pending_action"] == "answers"
    d.bot.get_chat_member.return_value = SimpleNamespace(status="member")
    await users.resume(callback("sub:check", msg), d.state, db, d.bot, d.redis, d.user)
    assert (await d.state.get_data())["pending_action"] is None


async def test_ref_start(db, domain):
    d = domain
    await users.start(message("/start ref_1", tg_id=2), d.state, db, d.bot, d.redis, d.user, True)
    assert d.user.referrer_id == d.owner.id
