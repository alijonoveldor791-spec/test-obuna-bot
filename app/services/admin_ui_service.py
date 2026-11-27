"""Permission-checked read-only admin views; interactive flows move to R5–R7."""

from typing import Any

from aiogram.types import BufferedInputFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User
from app.services import admin_service, export_service


async def export(message: Any, session: AsyncSession, user: User, kind: str, test_id: int) -> None:
    """Export existing data with live permission checks."""
    await admin_service.require(session, user.tg_id, "exports")
    content = await export_service.export(session, kind, test_id)
    await message.answer_document(BufferedInputFile(content, filename=f"{kind}-{test_id}.xlsx"))
