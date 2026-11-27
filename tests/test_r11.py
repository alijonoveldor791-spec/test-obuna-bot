"""Five-step creation, scheduling, access windows and reviewed result reports."""

from datetime import timedelta
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from openpyxl import load_workbook
from sqlalchemy import select

from app.config import settings
from app.db.base import utcnow
from app.db.models import AccessLog, Admin, Channel, Test
from app.repositories.tests import latest
from app.scheduler import jobs
from app.scheduler import setup as jobs_setup
from app.services import application_service as app
from app.services import test_creation_service as creation
from app.services import test_manage_service as manage
from app.services import test_time_service as time_service
from app.services.answer_parser import parse_key
from app.services.grading_service import submit
from app.services.post_service import publish, results
from app.services.test_time_service import aware, beginning, display, ending
from app.states.add_test import AddTest
from app.texts import t
from tests.test_scheduler import MemoryRedis


async def send(d, db, value):
    """Pass a reply through the full application dispatcher."""
    d.message.text = value
    await app.message(d.message, d.state, db, d.bot, d.redis, d.owner, False)


async def pdf(d, db, caption=None, name="math_test-1.pdf"):
    """Start with a real downloaded PDF and automatic metadata."""
    await send(d, db, t("new_test"))
    assert "1/5" in d.message.answer.await_args.args[0]
    d.message.document = SimpleNamespace(
        mime_type="application/pdf", file_size=100, file_id="new_pdf", file_name=name
    )
    d.message.caption = caption
    await send(d, db, "")
    d.message.document = None
    d.message.caption = None
    assert "2/5" in d.message.answer.await_args.args[0]


async def preview(d, db, start="start_now", end="day1", referral="ref3"):
    """Finish four directed answers and cache the preview photo."""
    await pdf(d, db)
    for value in ("1a,2b,3c", t(start), t(end), t(referral)):
        await send(d, db, value)
    assert await d.state.get_state() == AddTest.confirm.state
    draft = (await d.state.get_data())["draft"]
    assert draft["questions_count"] == 3 and draft["preview_file_id"]
    return draft


@pytest.mark.parametrize(
    "caption,name,title",
    [
        ("Caption title", "ignored.pdf", "Caption title"),
        (None, "math_test-1.pdf", "math test 1"),
        ("x" * 220, "ignored.pdf", "x" * 200),
    ],
)
async def test_pdf_metadata(db, domain, caption, name, title):
    d = domain
    await pdf(d, db, caption, name)
    draft = (await d.state.get_data())["draft"]
    assert draft["title"] == title and 1000 <= int(draft["code"]) <= 9999
    assert draft["code"] != d.test.code
    path = Path(draft["pdf_path"])
    await send(d, db, t("cancel_input"))
    assert not path.exists() and await d.state.get_state() is None


@pytest.mark.parametrize("finish", ["publish", "send_me"])
async def test_immediate_finish_and_cached_photo(db, domain, finish):
    d = domain
    draft = await preview(d, db)
    assert t("preview_summary", questions=3, referral=3) == d.message.answer.await_args.args[0]
    caption = d.message.answer_photo.await_args.kwargs["caption"]
    assert draft["title"] in caption and "Muddat:" in caption
    Path(draft["pdf_path"]).unlink()
    await send(d, db, t(finish))
    row = await db.scalar(select(Test).where(Test.code == draft["code"]))
    assert row.status == "active" and row.scheduled_at is None
    assert (aware(row.end_at) - aware(row.start_at)).total_seconds() == 86400
    assert d.bot.send_photo.await_args.args[0] == (
        d.owner.tg_id if finish == "send_me" else d.channel.tg_chat_id
    )


@pytest.mark.parametrize(
    "end,days", [("day1", 1), ("day3", 3), ("day7", 7), ("unlimited_btn", None)]
)
@pytest.mark.parametrize(
    "referral,count", [("no_referral", 0), ("ref3", 3), ("ref5", 5), ("ref10", 10)]
)
async def test_scheduled_shortcuts(db, domain, end, days, referral, count):
    d = domain
    draft = await preview(d, db, "start_tomorrow", end, referral)
    assert draft["referral_count"] == count
    assert creation.preview_keys(await d.state.get_data()) == [
        "schedule",
        "edit_post",
        "cancel_input",
    ]
    with pytest.raises(ValueError):
        # A stale immediate-publication button cannot schedule or publish.
        await publish(db, d.bot, d.test.id + 9999)
    await send(d, db, t("send_me"))
    assert await d.state.get_state() == AddTest.confirm.state
    await send(d, db, t("schedule"))
    row = await db.scalar(select(Test).where(Test.code == draft["code"]))
    assert row.status == "draft" and row.scheduled_at == row.start_at
    if days:
        assert (aware(row.end_at) - aware(row.start_at)).days == days
    else:
        assert row.end_at is None
    d.bot.send_photo.assert_not_awaited()


async def test_key_dates_referral_and_channel_errors(db, domain):
    d = domain
    db.add(Channel(tg_chat_id=-1002, title="Other"))
    await db.flush()
    await pdf(d, db)
    for value in ("1a,3b", "1a,1b", "0a,1b"):
        with pytest.raises(ValueError):
            await send(d, db, value)
    assert "2" in str(pytest.raises(ValueError, parse_key, "1a,3b").value)
    await send(d, db, "ab")
    for value in ("bad", "2020-01-01 10:00", "2026-02-30 10:00"):
        with pytest.raises(ValueError):
            await send(d, db, value)
    future = (
        (utcnow() + timedelta(days=3))
        .astimezone(beginning(t("start_tomorrow"))[0].tzinfo)
        .strftime("%Y-%m-%d %H:%M")
    )
    await send(d, db, future)
    with pytest.raises(ValueError):
        await send(d, db, future)
    await send(d, db, t("day3"))
    with pytest.raises(ValueError):
        await send(d, db, "5")
    await send(d, db, t("ref5"))
    choices = (await d.state.get_data())["channel_choices"]
    with pytest.raises(ValueError):
        await send(d, db, "1")
    await send(d, db, next(iter(choices)))
    await send(d, db, t("back"))
    assert creation.FIELDS[(await d.state.get_data())["field_index"]] == "channel_id"


async def test_not_started_and_admin_deep_link(db, domain):
    d = domain
    d.test.status = "draft"
    d.test.start_at = utcnow() + timedelta(days=1)
    d.test.scheduled_at = d.test.start_at
    await db.flush()
    assert await latest(db) is None
    for text in ("4829", "4829 ab"):
        with pytest.raises(ValueError, match="Test hali boshlanmagan"):
            await submit(db, d.user, text)
    with pytest.raises(ValueError):
        await publish(db, d.bot, d.test.id)
    for payload in ("test_" + str(d.test.id), "test", "ref_2"):
        await send(d, db, "/start " + payload)
        assert (await d.state.get_data())["nav_menu"] == "user"
    await send(d, db, "/start test_" + str(d.test.id))
    assert t("not_started", start=display(d.test.start_at)) == d.message.answer.await_args.args[0]
    d.bot.send_document.assert_not_awaited()


async def test_scheduled_cancel_confirmation_and_stale_role(db, domain):
    d = domain
    await preview(d, db, "start_tomorrow")
    await send(d, db, t("schedule"))
    row = await db.get(Test, (await d.state.get_data())["test_id"])
    await send(d, db, t("delete"))
    assert await d.state.get_state() == manage.CONFIRM_STATE
    await send(d, db, t("no"))
    assert await db.get(Test, row.id)
    await send(d, db, t("delete"))
    admin = await db.scalar(select(Admin).where(Admin.tg_id == d.owner.tg_id))
    admin.role = "moderator"
    await db.flush()
    with pytest.raises(PermissionError):
        await send(d, db, t("yes"))


async def test_results_and_combined_excel(db, domain):
    d = domain
    await submit(db, d.user, "ab")
    db.add(AccessLog(test_id=d.test.id, user_id=d.user.id))
    await db.flush()
    await manage.card(d.message, d.state, db, d.owner, d.test.id)
    await send(d, db, t("test_stats"))
    text = d.message.answer.await_args.args[0]
    assert "Topshirganlar: 1" in text and "Student" in text and "2 ta" in text
    await send(d, db, t("excel_results"))
    book = load_workbook(BytesIO(d.message.answer_document.await_args.args[0].data))
    assert book.sheetnames == ["Natijalar", "Testni olganlar"]
    assert all(book[name].max_row == 2 for name in book.sheetnames)
    with pytest.raises(ValueError):
        await results(db, d.bot, d.test.id)
    await send(d, db, t("close"))
    await send(d, db, t("yes"))
    assert aware(d.test.end_at) <= utcnow()
    d.bot.send_message.reset_mock()
    await send(d, db, t("announce"))
    await send(d, db, t("yes"))
    d.bot.send_message.assert_awaited_once()
    assert d.bot.send_message.await_args.args[0] == d.channel.tg_chat_id
    assert "TOP-10" in d.bot.send_message.await_args.args[1]
    with pytest.raises(ValueError):
        await results(db, d.bot, d.test.id)


@pytest.mark.parametrize("fail", [False, True])
async def test_scheduler_due_recovery_and_three_failures(db, domain, monkeypatch, fail):
    d = domain
    d.test.status = "draft"
    d.test.start_at = utcnow() - timedelta(hours=2)
    d.test.scheduled_at = d.test.start_at
    d.test.end_at = utcnow() + timedelta(hours=1)
    await db.flush()

    class Context:
        async def __aenter__(self):
            return db

        async def __aexit__(self, *args):
            await db.flush()

    class Factory:
        def __call__(self):
            return Context()

        def begin(self):
            return Context()

    monkeypatch.setattr(jobs, "sessions", Factory())
    redis = MemoryRedis()
    clock = [1000.0]
    monkeypatch.setattr(jobs.time, "time", lambda: clock[0])
    alert = AsyncMock()
    monkeypatch.setattr(jobs, "notify_admins", alert)
    if fail:
        d.bot.send_photo.side_effect = RuntimeError("network")
    for increment in (0, 0, 30, 60, 1000):
        clock[0] += increment
        await jobs.tick(d.bot, redis)
    if fail:
        assert d.bot.send_photo.await_count == 3
        alert.assert_awaited_once()
        assert d.test.status == "draft"
    else:
        d.bot.send_photo.assert_awaited_once()
        assert d.test.status == "active" and d.test.scheduled_at is None
        d.test.end_at = utcnow() - timedelta(seconds=1)
        await db.flush()
        await jobs.tick(d.bot, redis)
        assert d.test.status == "closed"


def test_date_timezone_and_ten_minute_boundary(monkeypatch):
    monkeypatch.setattr(settings, "tz", "Asia/Tashkent")
    start, _ = beginning("2099-12-01 10:00")
    assert str(start.tzinfo) == "Asia/Tashkent"
    assert ending("2099-12-01 10:10", start) - start == timedelta(minutes=10)
    with pytest.raises(ValueError):
        ending("2099-12-01 10:09", start)


async def test_invalid_pdf_and_explicit_dates(db, domain):
    d = domain
    await send(d, db, t("new_test"))
    for document in (
        None,
        SimpleNamespace(mime_type="text/plain", file_size=10),
        SimpleNamespace(mime_type="application/pdf", file_size=21 * 1024 * 1024),
    ):
        d.message.document = document
        with pytest.raises(ValueError):
            await send(d, db, "")
    await send(d, db, t("cancel_input"))
    await pdf(d, db)
    await send(d, db, "ab")
    await send(d, db, "2099-12-01 10:00")
    await send(d, db, "2099-12-01 11:00")
    await send(d, db, t("no_referral"))
    draft = (await d.state.get_data())["draft"]
    assert "01.12 10:00 – 01.12 11:00" in d.message.answer_photo.await_args.kwargs["caption"]
    assert draft["end_at"].endswith("+05:00")


async def test_active_future_is_not_latest_or_accepted(db, domain):
    d = domain
    d.test.start_at = utcnow() + timedelta(days=1)
    await db.flush()
    assert await latest(db) is None
    with pytest.raises(ValueError):
        await submit(db, d.user, "ab")


async def test_scheduled_list_pages_and_exact_menu(db, domain):
    d = domain
    for index in range(9):
        row = Test(
            code=str(6000 + index),
            title=f"Future {index}",
            pdf_file_id="pdf",
            pdf_path="none",
            questions_count=1,
            answer_key={"1": "a"},
            status="draft",
            start_at=utcnow() + timedelta(days=1),
            scheduled_at=utcnow() + timedelta(days=1),
            created_by=1,
        )
        db.add(row)
    await db.flush()
    await send(d, db, t("tests"))
    labels = [
        b.text for row in d.message.answer.await_args.kwargs["reply_markup"].keyboard for b in row
    ]
    assert labels[:2] == [t("active"), t("closed")]
    await send(d, db, t("active"))
    choices = (await d.state.get_data())["test_choices"]
    assert len(choices) == 8 and all(label.startswith("⏰ #") for label in choices)
    await send(d, db, t("next_page"))
    assert len((await d.state.get_data())["test_choices"]) == 2
    await send(d, db, t("previous_page"))
    await send(d, db, next(iter((await d.state.get_data())["test_choices"])))
    labels = [
        b.text for row in d.message.answer.await_args.kwargs["reply_markup"].keyboard for b in row
    ]
    assert labels == [t("edit_post"), t("delete"), t("back"), t("home")]


async def test_preview_permission_revoked_and_post_error_retains_state(db, domain):
    d = domain
    await preview(d, db)
    d.bot.send_photo.side_effect = RuntimeError("network")
    with pytest.raises(RuntimeError):
        await send(d, db, t("publish"))
    assert await d.state.get_state() == AddTest.confirm.state
    admin = await db.scalar(select(Admin).where(Admin.tg_id == d.owner.tg_id))
    admin.role = "moderator"
    await db.flush()
    with pytest.raises(PermissionError):
        await send(d, db, t("publish"))


def test_scheduler_runs_deadline_scan_on_startup():
    scheduler = jobs_setup.create_scheduler(None, None)
    job = scheduler.get_job("tick")
    assert job.next_run_time <= utcnow()


async def test_window_minute_grace_and_questions(db, domain, monkeypatch):
    fixed = utcnow().replace(second=30, microsecond=0)
    monkeypatch.setattr(time_service, "utcnow", lambda: fixed)
    start, immediate = beginning(
        (fixed - timedelta(seconds=10))
        .astimezone(time_service.ZoneInfo(settings.tz))
        .strftime("%Y-%m-%d %H:%M")
    )
    assert immediate and start >= fixed - timedelta(minutes=1)
    d = domain
    await pdf(d, db)
    for number, value in ((3, "ab"), (4, t("start_now")), (5, t("day1"))):
        await send(d, db, value)
        assert f"{number}/5" in d.message.answer.await_args.args[0]
