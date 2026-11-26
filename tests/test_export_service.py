"""Reports open cleanly and neutralize spreadsheet formulas."""

from io import BytesIO

from openpyxl import load_workbook

from app.db.models import AccessLog, Referral, Submission, Test, User
from app.services.export_service import export, workbook


def test_large_workbook():
    data = workbook(["Name", "Value"], (("=HYPERLINK(x)", i) for i in range(10001)))
    book = load_workbook(BytesIO(data), read_only=False)
    sheet = book.active
    assert sheet.max_row == 10002 and sheet.freeze_panes == "A2"
    assert sheet["A2"].value.startswith("'=")


async def test_all_reports(db):
    user = User(tg_id=11, full_name="Ali")
    other = User(tg_id=12, full_name="Vali")
    test = Test(
        code="1234",
        title="Test",
        pdf_file_id="file",
        pdf_path="f",
        questions_count=1,
        answer_key={"1": "a"},
        created_by=1,
    )
    db.add_all([user, other, test])
    await db.flush()
    db.add_all(
        [
            Submission(
                test_id=test.id,
                user_id=user.id,
                answers={"1": "a"},
                correct_count=1,
                wrong_count=0,
                score_percent=100,
            ),
            AccessLog(test_id=test.id, user_id=user.id),
            Referral(inviter_id=user.id, invited_id=other.id),
        ]
    )
    await db.flush()
    for kind in ("users", "results", "access", "refs"):
        book = load_workbook(BytesIO(await export(db, kind, test.id)), read_only=True)
        assert len(list(book.active.rows)) >= 2
