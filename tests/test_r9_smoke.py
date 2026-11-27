"""One complete conversation smoke flow against SQLite and PostgreSQL."""

from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from openpyxl import load_workbook
from sqlalchemy import func, select

from app.db.models import AccessLog, Admin, Channel, Submission, Test, User
from app.services import application_service as application
from app.services import test_manage_service as management
from app.texts import t
from tests.helpers import MemoryState, bot, callback, message


async def smoke(session) -> None:
    """Exercise creation, subscription, referral, export, close and announcement."""
    owner = User(tg_id=901, full_name="Owner")
    student = User(tg_id=902, full_name="Student")
    channel = Channel(
        tg_chat_id=-100901,
        title="Smoke channel",
        username="smoke_channel",
        is_main=True,
        is_required=True,
    )
    session.add_all([owner, student, channel, Admin(tg_id=owner.tg_id, role="owner")])
    await session.flush()
    api = bot()
    redis = SimpleNamespace(get=AsyncMock(return_value=None), set=AsyncMock(return_value=True))
    admin_state, user_state = MemoryState(), MemoryState()
    admin_message, user_message = message(tg_id=owner.tg_id), message(tg_id=student.tg_id)

    async def admin(text: str) -> None:
        admin_message.text = text
        await application.message(admin_message, admin_state, session, api, redis, owner, False)

    await admin("/start")
    await admin(t("new_test"))
    admin_message.document = SimpleNamespace(
        mime_type="application/pdf", file_size=100, file_id="smoke_pdf", file_name="smoke_test.pdf"
    )
    await admin("")
    admin_message.document = None
    for text in ("1a,2b", t("start_now"), t("day1"), t("ref3")):
        await admin(text)
    await admin(t("publish"))
    test = await session.scalar(select(Test))
    assert test.status == "active" and test.referral_count == 3
    post_markup = api.send_photo.await_args.kwargs["reply_markup"]
    assert post_markup.inline_keyboard[0][0].url.endswith("?start=test")

    api.get_chat_member.return_value = SimpleNamespace(status="left")
    user_message.text = "/start test"
    await application.message(user_message, user_state, session, api, redis, student, True)
    api.send_document.assert_not_awaited()
    assert (await user_state.get_data())["pending_action"] == "test"
    api.get_chat_member.return_value = SimpleNamespace(status="member")
    await application.callback(
        callback("sub:check", user_message), user_state, session, api, redis, student
    )
    api.send_document.assert_awaited_once()
    assert await session.scalar(select(func.count()).select_from(AccessLog)) == 1

    user_message.text = test.code + " 1a,2b"
    with pytest.raises(ValueError, match="3"):
        await application.message(user_message, user_state, session, api, redis, student, False)
    assert await session.scalar(select(func.count()).select_from(Submission)) == 0

    for index in range(3):
        invited = User(tg_id=910 + index, full_name=f"Invited {index}")
        session.add(invited)
        await session.flush()
        invited_message = message(f"/start ref_{student.tg_id}", tg_id=invited.tg_id)
        await application.message(
            invited_message, MemoryState(), session, api, redis, invited, True
        )
        assert invited.is_subscribed and invited.referrer_id == student.id
    await application.message(user_message, user_state, session, api, redis, student, False)
    result = await session.scalar(select(Submission))
    assert result.correct_count == 2 and result.score_percent == 100

    await management.card(admin_message, admin_state, session, owner, test.id)
    await admin(t("test_stats"))
    assert "Referral talabini to‘ldirganlar: 1" in admin_message.answer.await_args.args[0]
    await admin(t("excel_results"))
    book = load_workbook(BytesIO(admin_message.answer_document.await_args.args[0].data))
    assert book.sheetnames == ["Natijalar", "Testni olganlar"]
    assert "Student" in str(list(book["Natijalar"].values))
    book.close()
    await admin(t("close"))
    assert test.status == "active"
    await admin(t("yes"))
    assert test.status == "closed"
    api.send_message.reset_mock()
    await admin(t("announce"))
    await admin(t("yes"))
    api.send_message.assert_awaited_once()
    assert api.send_message.await_args.args[0] == channel.tg_chat_id
    assert "TOP-10" in api.send_message.await_args.args[1]
    assert test.results_published
    await admin(t("announce"))
    with pytest.raises(ValueError):
        await admin(t("yes"))
    api.send_message.assert_awaited_once()


async def test_smoke_sqlite(db, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    await smoke(db)


async def test_smoke_postgres(postgres_factory, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    async with postgres_factory.begin() as session:
        await smoke(session)
