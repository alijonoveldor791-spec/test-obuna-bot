"""R6 statistics, exports, directed moderation and test-card operations."""

from datetime import timedelta
from io import BytesIO

import pytest
from openpyxl import load_workbook
from sqlalchemy import select

from app.db.base import utcnow
from app.db.models import AccessLog, Admin, Referral, Submission, User
from app.repositories import stats
from app.services import application_service as app
from app.services import test_manage_service as manage
from app.services.grading_service import submit
from app.services.reporting_service import USER_INPUT
from app.texts import t


async def send(d, db, key, raw=False):
    d.message.text = key if raw else t(key)
    await app.message(d.message, d.state, db, d.bot, d.redis, d.owner, False)


async def test_statistics_match_database(db, domain):
    d = domain
    db.add(AccessLog(test_id=d.test.id, user_id=d.user.id))
    await db.flush()
    await submit(db, d.user, "ab")
    values = await stats.for_test(db, d.test)
    assert values["access"] == values["submitted"] == 1
    assert values["average"] == 100 and "100.0%" in values["questions"]
    general = await stats.general(db)
    assert general["total"] == general["today"] == 2
    await send(d, db, "stats")
    await send(d, db, "general")
    assert "Foydalanuvchilar: 2" in d.message.answer.await_args.args[0]
    await manage.card(d.message, d.state, db, d.owner, d.test.id)
    await send(d, db, "test_stats")
    assert "Topshirganlar: 1" in d.message.answer.await_args.args[0]


async def test_referral_top_ignores_unsubscribed(db, domain):
    d = domain
    db.add(Referral(inviter_id=d.owner.id, invited_id=d.user.id, is_valid=True))
    await db.flush()
    assert (await stats.general(db))["refs"] == "?"
    d.user.is_subscribed = True
    await db.flush()
    await send(d, db, "stats")
    await send(d, db, "ref_top")
    assert "Owner: 1" in d.message.answer.await_args.args[0]


async def test_ban_unban_and_protected_admin(db, domain):
    d = domain
    d.user.username = "student"
    await db.flush()
    await send(d, db, "users")
    await send(d, db, "ban_btn")
    assert await d.state.get_state() == USER_INPUT
    with pytest.raises(ValueError):
        await send(d, db, "ban 2", raw=True)
    await send(d, db, "@STUDENT", raw=True)
    assert d.user.is_banned and await d.state.get_state() is None
    await send(d, db, "banned_btn")
    assert "Student" in d.message.answer.await_args.args[0]
    await send(d, db, "unban_btn")
    await send(d, db, "2", raw=True)
    assert not d.user.is_banned
    await send(d, db, "ban_btn")
    with pytest.raises(PermissionError):
        await send(d, db, "1", raw=True)


async def test_export_sections_and_test_files(db, domain):
    d = domain
    await submit(db, d.user, "ab")
    db.add(AccessLog(test_id=d.test.id, user_id=d.user.id))
    await db.flush()
    await send(d, db, "exports")
    for key in ("export_users", "export_refs"):
        await send(d, db, key)
        file = d.message.answer_document.await_args.args[0]
        assert load_workbook(BytesIO(file.data)).active.max_row >= 1
    await manage.card(d.message, d.state, db, d.owner, d.test.id)
    for key in ("excel_results",):
        await send(d, db, key)
        file = d.message.answer_document.await_args.args[0]
        rows = list(load_workbook(BytesIO(file.data)).active.values)
        assert "Student" in str(rows) and len(rows) == 2


async def test_key_edit_recalculates_and_deadline_input(db, domain):
    d = domain
    row, _, _ = await submit(db, d.user, "aa")
    assert row.correct_count == 1
    await manage.card(d.message, d.state, db, d.owner, d.test.id)
    await send(d, db, "key")
    with pytest.raises(ValueError):
        await send(d, db, "1a,2e", raw=True)
    await send(d, db, "aa", raw=True)
    assert row.correct_count == 2 and row.rank == 1


async def test_announcement_requires_confirmation_and_runs_once(db, domain):
    d = domain
    await submit(db, d.user, "ab")
    await manage.card(d.message, d.state, db, d.owner, d.test.id)
    await send(d, db, "close")
    await send(d, db, "yes")
    await send(d, db, "announce")
    before = d.bot.send_message.await_count
    assert not d.test.results_published
    await send(d, db, "no")
    assert d.bot.send_message.await_count == before
    await send(d, db, "announce")
    await send(d, db, "yes")
    assert d.test.results_published
    assert d.channel.tg_chat_id in {call.args[0] for call in d.bot.send_message.await_args_list}
    assert d.user.tg_id not in {call.args[0] for call in d.bot.send_message.await_args_list}
    await send(d, db, "announce")
    with pytest.raises(ValueError):
        await send(d, db, "yes")


async def test_ranking_ties_paging_and_moderator_access(db, domain):
    d = domain
    for i in range(22):
        person = User(tg_id=100 + i, full_name=f"Person {i}")
        db.add(person)
        await db.flush()
        db.add(
            Submission(
                test_id=d.test.id,
                user_id=person.id,
                answers={"1": "a", "2": "b"},
                correct_count=2,
                wrong_count=0,
                score_percent=100,
                submitted_at=utcnow() + timedelta(seconds=i),
            )
        )
    admin = await db.scalar(select(Admin).where(Admin.tg_id == 1))
    admin.role = "moderator"
    await db.flush()
    await manage.card(d.message, d.state, db, d.owner, d.test.id)
    await send(d, db, "test_stats")
    text = d.message.answer.await_args.args[0]
    assert "1. Person 0" in text and "10. Person 9" in text and "11. Person 10" not in text
    with pytest.raises(PermissionError):
        await send(d, db, "key")


async def test_username_underscore_is_literal(db, domain):
    d = domain
    d.user.username = "studentxname"
    target = User(tg_id=66, full_name="Exact", username="student_name")
    db.add(target)
    await db.flush()
    await send(d, db, "users")
    await send(d, db, "ban_btn")
    await send(d, db, "@student_name", raw=True)
    assert target.is_banned and not d.user.is_banned


async def test_input_permission_revocation_and_stale_test_state(db, domain):
    d = domain
    await manage.card(d.message, d.state, db, d.owner, d.test.id)
    await send(d, db, "key")
    d.test.status = "closed"
    await db.flush()
    with pytest.raises(ValueError):
        await send(d, db, "aa", raw=True)
    await send(d, db, "cancel_input")
    await send(d, db, "users")
    await send(d, db, "ban_btn")
    admin = await db.scalar(select(Admin).where(Admin.tg_id == 1))
    admin.role = "moderator"
    await db.flush()
    with pytest.raises(PermissionError):
        await send(d, db, "2", raw=True)
    assert not d.user.is_banned
