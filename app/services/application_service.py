"""Private conversation routing with two supported commands."""

import re
from typing import Any

from aiogram import Bot
from aiogram.fsm.context import FSMContext
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User
from app.services import nav_service as nav
from app.services import test_creation_service as creation
from app.services import user_service as users
from app.services.admin_service import require, role
from app.states.add_test import AddTest
from app.texts import t


async def message(
    message: Any,
    state: FSMContext,
    session: AsyncSession,
    bot: Bot,
    redis: Redis,
    user: User,
    is_new: bool,
) -> None:
    """Route commands, navigation, current input and direct participant answers."""
    user.lang = "uz"
    text = message.text or ""
    command = text.split(maxsplit=1)[0].split("@")[0] if text.strip() else ""
    if command in ("/start", "/admin"):
        if command == "/admin":
            await require(session, user.tg_id, "panel")
        if await state.get_state() in (
            AddTest.pdf.state,
            AddTest.fields.state,
            AddTest.confirm.state,
        ) or (
            await state.get_state() in (nav.management.POST_INPUT, nav.management.POST_CONFIRM)
            and (await state.get_data()).get("post_origin") == "preview"
        ):
            await creation.discard(state)
        await nav.broadcasting.discard(state, session)
        await state.clear()
        payload = text.split(maxsplit=1)
        payload = payload[1] if len(payload) > 1 else ""
        if command == "/start" and (payload == "test" or payload.startswith(("test_", "ref_"))):
            await state.update_data(nav_menu="user")
            await users.start(message, state, session, bot, redis, user, is_new)
        elif await role(session, user.tg_id):
            await nav.show(message, state, session, user, "admin")
        else:
            await state.update_data(nav_menu="user")
            await users.start(message, state, session, bot, redis, user, is_new)
        return
    if text.startswith("/"):
        if await state.get_state():
            await message.answer(t("input_controls"), reply_markup=nav.reply.input_menu())
        else:
            await nav.show(message, state, session, user)
        return
    if await nav.handle(message, state, session, bot, redis, user):
        return
    current = await state.get_state()
    if current in (AddTest.pdf.state, AddTest.fields.state):
        await require(session, user.tg_id, "tests")
        handler = creation.receive_pdf if current == AddTest.pdf.state else creation.field_value
        if current == AddTest.pdf.state:
            await handler(message, state, session, bot)
        else:
            await handler(message, state, session)
    elif current:
        await message.answer(t("input_controls"), reply_markup=nav.reply.input_menu())
    elif re.match(r"^(?:[0-9]|[a-dA-D]+$)", text):
        await users.answers(message, state, session, bot, redis, user)
    else:
        await nav.show(message, state, session, user)


async def callback(
    callback: Any, state: FSMContext, session: AsyncSession, bot: Bot, redis: Redis, user: User
) -> None:
    """Only subscription refresh callbacks are supported."""
    await callback.answer()
    if callback.data == "sub:check":
        await users.resume(callback, state, session, bot, redis, user)
