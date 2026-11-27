"""Reply section statistics, exports and directed ban/unban input."""

from typing import Any

from aiogram.fsm.context import FSMContext
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User
from app.keyboards.reply import build, input_menu
from app.repositories import stats
from app.services import admin_service
from app.services.admin_ui_service import export
from app.services.errors import BusinessError
from app.services.menu_service import show
from app.texts import t
from app.utils.formatting import chunks

USER_INPUT = "Reports:user"
PERMISSIONS = {
    "general": "stats",
    "ref_top": "stats",
    "export_users": "exports",
    "export_refs": "exports",
    "ban_btn": "users",
    "unban_btn": "users",
    "banned_btn": "users",
}


async def action(
    message: Any, state: FSMContext, session: AsyncSession, user: User, key: str
) -> None:
    """Execute a section action after a live role check."""
    await admin_service.require(session, user.tg_id, PERMISSIONS[key])
    if key in ("general", "ref_top"):
        values = await stats.general(session)
        for part in chunks(t("general_stats" if key == "general" else "ref_top_body", **values)):
            await message.answer(part, parse_mode=None)
    elif key in ("export_users", "export_refs"):
        await export(message, session, user, key.removeprefix("export_"), 0)
    elif key in ("ban_btn", "unban_btn"):
        await state.update_data(nav_menu="users", user_action=key)
        await state.set_state(USER_INPUT)
        await message.answer(t("target_user"), reply_markup=input_menu())
    else:
        await banned(message, state, session, user, 0)


async def banned(
    message: Any, state: FSMContext, session: AsyncSession, user: User, page: int
) -> None:
    """Page through banned users without losing the users-section parent."""
    await admin_service.require(session, user.tg_id, "users")
    page = max(0, page)
    rows = list(
        (
            await session.scalars(
                select(User)
                .where(User.is_banned.is_(True))
                .order_by(User.id)
                .offset(page * 20)
                .limit(21)
            )
        ).all()
    )
    if not rows and page:
        return await banned(message, state, session, user, page - 1)
    keys = (["previous_page"] if page else []) + (["next_page"] if len(rows) > 20 else [])
    await state.update_data(nav_menu="users", banned_view=True, banned_page=page)
    text = "\n".join(
        t("banned_row", tg_id=row.tg_id, name=row.full_name, username=row.username or "?")
        for row in rows[:20]
    ) or t("empty")
    for part in chunks(text):
        await message.answer(part, reply_markup=build(keys, footer=True), parse_mode=None)


async def handle(message: Any, state: FSMContext, session: AsyncSession, user: User) -> bool:
    """Consume directed user lookup input and banned-list pagination."""
    data = await state.get_data()
    current = await state.get_state()
    text = (message.text or "").strip()
    if current == USER_INPUT:
        await admin_service.require(session, user.tg_id, "users")
        if text.isascii() and text.isdigit():
            query = select(User).where(User.tg_id == int(text))
        elif text.startswith("@") and text[1:].replace("_", "").isalnum():
            query = select(User).where(func.lower(User.username) == text[1:].lower())
        else:
            raise BusinessError(t("target_user"))
        target = await session.scalar(query.with_for_update())
        if target is None:
            raise BusinessError(t("empty"))
        if await admin_service.role(session, target.tg_id):
            raise PermissionError(t("denied"))
        target.is_banned = data["user_action"] == "ban_btn"
        await session.flush()
        await state.set_state(None)
        await state.update_data(banned_view=False)

        await message.answer(t("ban_saved" if target.is_banned else "unban_saved"))
        await show(message, state, session, user, "users")
        return True
    if (
        not current
        and data.get("nav_menu") == "users"
        and data.get("banned_view")
        and text in (t("previous_page"), t("next_page"))
    ):
        await banned(
            message,
            state,
            session,
            user,
            data.get("banned_page", 0) + (1 if text == t("next_page") else -1),
        )
        return True
    return False
