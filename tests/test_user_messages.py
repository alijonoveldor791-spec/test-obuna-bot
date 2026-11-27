"""Participant instructions use live test data and explain required actions."""

from types import SimpleNamespace

from app.services import application_service as app
from app.services import user_service as users
from app.texts import t


async def press(d, db, key):
    d.message.text = t(key)
    await app.message(d.message, d.state, db, d.bot, d.redis, d.user, False)


async def test_answer_prompt_real_code_and_count(db, domain):
    d = domain
    d.test.code = "5833"
    await db.flush()
    await press(d, db, "submit_btn")
    text = d.message.answer.await_args.args[0]
    assert "<pre>5833 1?,2?</pre>" in text and "4829" not in text
    assert "Savollar: 2 ta" in text and d.test.title in text
    assert await d.state.get_state() == "Navigation:answers"
    await press(d, db, "back")
    assert (await d.state.get_data())["nav_menu"] == "user"


async def test_no_active_test_does_not_enter_answers(db, domain):
    d = domain
    d.test.status = "closed"
    await db.flush()
    await press(d, db, "submit_btn")
    assert await d.state.get_state() is None
    assert d.message.answer.await_args.args[0] == t("no_test")


async def test_referral_single_message_and_remaining(db, domain):
    d = domain
    d.test.referral_required = True
    d.test.referral_count = 3
    await db.flush()
    d.message.answer.reset_mock()
    await press(d, db, "referral")
    d.message.answer.assert_awaited_once()
    text = d.message.answer.await_args.args[0]
    assert "0 / 3" in text and "Yana 3 ta" in text
    assert f"start=ref_{d.user.tg_id}" in text
    assert "test boshlanganidan keyingi" in text
    d.test.referral_count = 0
    await db.flush()
    await users.referral(d.message, db, d.user)
    assert "✅ Taklif talabi bajarildi" in d.message.answer.await_args.args[0]


async def test_optional_and_no_test_referral(db, domain):
    d = domain
    await users.referral(d.message, db, d.user)
    assert "majburiy emas" in d.message.answer.await_args.args[0]
    d.test.status = "closed"
    await db.flush()
    await users.referral(d.message, db, d.user)
    assert "Hozir faol test yo‘q" in d.message.answer.await_args.args[0]


async def test_results_empty_and_no_duplicate_help(db, domain):
    d = domain
    await press(d, db, "results")
    d.message.answer.assert_awaited_once()
    assert d.message.answer.await_args.args[0] == t("no_results")
    d.message.answer.reset_mock()
    await press(d, db, "help_btn")
    d.message.answer.assert_awaited_once()
    assert "4829" not in d.message.answer.await_args.args[0]


async def test_copyable_sample_does_not_leak_answers(db, domain):
    d = domain
    d.test.title = "<Test> & example"
    d.test.questions_count = 30
    await db.flush()
    await press(d, db, "submit_btn")
    text = d.message.answer.await_args.args[0]
    assert "1?,2?,3?" in text and "30?</pre>" in text
    assert "1a" not in text and "2b" not in text
    assert "&lt;Test&gt; &amp; example" in text
    assert d.message.answer.await_args.kwargs["parse_mode"] == "HTML"
    await users.send_test(d.message, d.state, db, d.bot, d.redis, d.user)
    text = d.message.answer.await_args.args[0]
    assert "<pre>" in text and "30?</pre>" in text
    assert d.message.answer.await_args.kwargs["parse_mode"] == "HTML"


def test_large_sample_stays_bounded():
    from_test = SimpleNamespace(code="5833", questions_count=1000)
    sample = users.answer_sample(from_test)
    assert len(sample) < 1000 and sample.endswith(",...")
