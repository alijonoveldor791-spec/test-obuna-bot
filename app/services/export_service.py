"""Bounded-memory Excel reports with safe spreadsheet text."""

import asyncio
import json
from collections.abc import Iterable
from datetime import datetime
from io import BytesIO
from tempfile import SpooledTemporaryFile

from openpyxl import Workbook, load_workbook
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
from openpyxl.utils import get_column_letter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AccessLog, Referral, Submission, User
from app.texts import headers, t


class Report:
    """Spool rows to disk while measuring column widths."""

    def __init__(self, columns: list[str]):
        self.columns = columns
        self.widths = [len(label) for label in columns]
        self.spool = SpooledTemporaryFile(max_size=1_000_000, mode="w+t", encoding="utf-8")

    def append(self, row: tuple) -> None:
        """Normalize one row and retain only a bounded in-memory spool."""
        clean = []
        for index, value in enumerate(row):
            if isinstance(value, datetime):
                value = value.isoformat()
            if isinstance(value, str):
                value = ILLEGAL_CHARACTERS_RE.sub("", value)[:32700]
                if value.startswith(("=", "+", "-", "@")):
                    value = "'" + value
            clean.append(value)
            self.widths[index] = min(60, max(self.widths[index], len(str(value or ""))))
        self.spool.write(json.dumps(clean) + "\n")

    def build(self) -> bytes:
        """Write rows in streaming mode and release the temporary file."""
        try:
            book = Workbook(write_only=True)
            sheet = book.create_sheet("Report")
            sheet.freeze_panes = "A2"
            for index, width in enumerate(self.widths, 1):
                sheet.column_dimensions[get_column_letter(index)].width = max(12, width + 2)
            sheet.append(self.columns)
            self.spool.seek(0)
            for line in self.spool:
                sheet.append(json.loads(line))
            result = BytesIO()
            book.save(result)
            return result.getvalue()
        finally:
            self.spool.close()


def workbook(columns: list[str], rows: Iterable[tuple]) -> bytes:
    """Build a write-only workbook with content-sized columns."""
    report = Report(columns)
    try:
        for row in rows:
            report.append(row)
        return report.build()
    finally:
        report.spool.close()


async def export(session: AsyncSession, kind: str, test_id: int | None = None) -> bytes:
    """Stream four report types without materializing the whole result set."""
    if kind == "results":
        query = (
            select(Submission, User)
            .join(User, User.id == Submission.user_id)
            .where(Submission.test_id == test_id)
            .order_by(Submission.rank.asc().nullslast(), Submission.submitted_at)
        )
    elif kind == "access":
        query = (
            select(User, AccessLog.got_at)
            .join(AccessLog, AccessLog.user_id == User.id)
            .where(AccessLog.test_id == test_id)
        )
    elif kind == "users":
        query = select(User).order_by(User.id)
    elif kind == "refs":
        query = select(Referral).order_by(Referral.id)
    else:
        raise ValueError(kind)
    report = Report(headers("headers_" + kind))
    index = 0
    try:
        stream = await session.stream(query.execution_options(yield_per=500))
        async for batch in stream.partitions(500):
            rows = []
            for record in batch:
                index += 1
                if kind == "results":
                    row, user = record
                    values = (
                        index,
                        user.full_name,
                        user.username,
                        user.tg_id,
                        row.correct_count,
                        row.wrong_count,
                        row.score_percent,
                        row.submitted_at,
                        row.rank,
                    )
                elif kind == "access":
                    user, when = record
                    values = (user.full_name, user.username, user.tg_id, when)
                elif kind == "users":
                    user = record[0]
                    values = (
                        user.full_name,
                        user.username,
                        user.tg_id,
                        user.is_subscribed,
                        user.joined_at,
                        user.referrer_id,
                    )
                else:
                    ref = record[0]
                    values = (ref.inviter_id, ref.invited_id, ref.is_valid, ref.created_at)
                rows.append(values)
            await asyncio.to_thread(_append_batch, report, rows)
        return await asyncio.to_thread(report.build)
    finally:
        report.spool.close()


def _append_batch(report: Report, rows: list[tuple]) -> None:
    """Keep workbook preparation off the Telegram event loop."""
    for row in rows:
        report.append(row)


async def test_report(session: AsyncSession, test_id: int) -> bytes:
    """Return one workbook with results and download sheets."""
    data = [await export(session, kind, test_id) for kind in ("results", "access")]
    return await asyncio.to_thread(_combine, data)


def _combine(data: list[bytes]) -> bytes:
    """Stream generated sheets into a single workbook."""
    workbook = Workbook(write_only=True)
    for title, content in zip((t("sheet_results"), t("sheet_access")), data, strict=True):
        source = load_workbook(BytesIO(content), read_only=True)
        sheet = workbook.create_sheet(title)
        for row in source.active.iter_rows(values_only=True):
            sheet.append(row)
        source.close()
    target = BytesIO()
    workbook.save(target)
    return target.getvalue()
