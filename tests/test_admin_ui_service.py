"""Guarded report delivery remains available after obsolete views are removed."""

import pytest

from app.services.admin_ui_service import export


async def test_report_delivery(db, domain):
    await export(domain.message, db, domain.owner, "users", 0)
    file = domain.message.answer_document.await_args.args[0]
    assert file.filename == "users-0.xlsx"
    assert file.data.startswith(b"PK")


async def test_report_requires_permission(db, domain):
    with pytest.raises(PermissionError):
        await export(domain.message, db, domain.user, "users", 0)
    domain.message.answer_document.assert_not_awaited()
