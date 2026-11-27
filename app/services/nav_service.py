"""Declaration-driven private-chat navigation with live authorization."""

from dataclasses import dataclass
from typing import Any

from aiogram import Bot
from aiogram.fsm.context import FSMContext
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User
from app.keyboards import reply
from app.menus import MENUS, permissions_for
from app.services import admin_service, user_service
from app.services import broadcast_ui_service as broadcasting
from app.services import reporting_service as reporting
from app.services import settings_ui_service as configuration
from app.services import test_creation_service as creation
from app.services import test_manage_service as management
from app.services.menu_service import button_key as button_key
from app.services.menu_service import show as show
from app.states.add_test import AddTest
from app.texts import t

ANSWER_STATE = "Navigation:answers"


@dataclass
class Context:
    """Dependencies for a declared navigation action."""

    message: Any
    state: FSMContext
    session: AsyncSession
    bot: Bot
    redis: Redis
    user: User
    key: str


async def open_menu(ctx: Context) -> None:
    """Open a declaration's child menu."""
    await show(ctx.message, ctx.state, ctx.session, ctx.user, ctx.key)


async def user_mode(ctx: Context) -> None:
    """Switch an administrator to participant navigation."""
    await show(ctx.message, ctx.state, ctx.session, ctx.user, "user")


async def participant(ctx: Context) -> None:
    """Run an existing participant service while preserving the user parent."""
    await ctx.state.update_data(nav_menu="user")
    calls = {
        "latest": lambda: user_service.send_test(
            ctx.message, ctx.state, ctx.session, ctx.bot, ctx.redis, ctx.user
        ),
        "results": lambda: user_service.my_results(ctx.message, ctx.session, ctx.user),
        "referral": lambda: user_service.referral(ctx.message, ctx.session, ctx.user),
    }
    await calls[ctx.key]()


async def answer_prompt(ctx: Context) -> None:
    """Enter answer input, returning to the participant menu on cancel."""
    await ctx.state.update_data(nav_menu="user")
    await user_service.answer_instructions(ctx.message, ctx.state, ctx.session)


async def help_page(ctx: Context) -> None:
    """Display Uzbek help and standard parent controls."""
    await ctx.state.update_data(nav_menu="user")
    await ctx.message.answer(t("help"), reply_markup=reply.user_menu())


async def test_flow(ctx: Context) -> None:
    """Route declared test actions into the R5 flow services."""
    if ctx.key == "new_test":
        await creation.start(ctx.message, ctx.state)
    elif ctx.key in ("active", "closed"):
        await management.list_page(ctx.message, ctx.state, ctx.session, ctx.user, ctx.key, 0)
    elif ctx.key in management.ACTION_PERMISSIONS:
        await management.action(ctx.message, ctx.state, ctx.session, ctx.bot, ctx.user, ctx.key)
    else:
        await show(ctx.message, ctx.state, ctx.session, ctx.user, ctx.key)


async def report_flow(ctx: Context) -> None:
    """Delegate declared R6 section actions."""
    await reporting.action(ctx.message, ctx.state, ctx.session, ctx.user, ctx.key)


async def settings_flow(ctx: Context) -> None:
    """Delegate directed owner operations."""
    await configuration.action(ctx.message, ctx.state, ctx.session, ctx.bot, ctx.user, ctx.key)


async def broadcast_flow(ctx: Context) -> None:
    """Delegate directed broadcast composition."""
    await broadcasting.start(ctx.message, ctx.state, ctx.session, ctx.user, ctx.key)


ACTIONS = {
    "settings_flow": settings_flow,
    "broadcast_flow": broadcast_flow,
    "report_flow": report_flow,
    "menu": open_menu,
    "test_flow": test_flow,
    "user": user_mode,
    "latest": participant,
    "results": participant,
    "referral": participant,
    "answers": answer_prompt,
    "help": help_page,
}


async def navigate(ctx: Context, key: str, current: str | None) -> None:
    """Clear FSM on navigation and follow the current declaration's parent."""
    data = await ctx.state.get_data()
    role = await admin_service.role(ctx.session, ctx.user.tg_id)
    menu_id = data.get("nav_menu", "admin" if role else "user")
    if menu_id not in MENUS:
        menu_id = "admin" if role else "user"
    destination = menu_id if current else MENUS[menu_id].parent or menu_id
    if key == "home":
        destination = (
            "admin" if role and menu_id != "user" and MENUS[menu_id].parent != "user" else "user"
        )
    if key == "cancel_input":
        destination = menu_id
    await ctx.state.clear()
    if destination in ("test_card", "test_list"):
        await ctx.state.update_data(
            **{
                key: data[key]
                for key in ("test_id", "test_filter", "test_page", "test_choices")
                if key in data
            }
        )
    if MENUS[destination].permission and not role:
        destination = "user"
    await show(ctx.message, ctx.state, ctx.session, ctx.user, destination)


async def handle(
    message: Any, state: FSMContext, session: AsyncSession, bot: Bot, redis: Redis, user: User
) -> bool:
    """Dispatch known buttons through the menu table before accepting answers."""
    text = message.text or ""
    if text.startswith("/"):
        return False
    key = button_key(text, (await state.get_data()).get("nav_menu"))
    current = await state.get_state()
    ctx = Context(message, state, session, bot, redis, user, key or "user")
    if key in ("back", "home", "cancel_input"):
        if current in (management.POST_INPUT, management.POST_CONFIRM):
            if key != "home":
                await management.return_post(message, state, session, user)
                return True
            if (await state.get_data()).get("post_origin") == "preview":
                await creation.discard(state)
        if key == "back" and current in (AddTest.fields.state, AddTest.confirm.state):
            await creation.back(message, state, session)
            return True
        if current in (AddTest.pdf.state, AddTest.fields.state, AddTest.confirm.state):
            await creation.discard(state)
        await broadcasting.discard(state, session)
        # Returning from input keeps the selected card or section, not a stale draft.
        await navigate(ctx, key, current)
        return True
    if await configuration.handle(message, state, session, bot, user):
        return True
    if await broadcasting.handle(message, state, session, user):
        return True
    if await reporting.handle(message, state, session, user):
        return True
    if await management.handle(message, state, session, bot, user):
        return True
    if key:
        entry = MENUS[key]
        for permission in permissions_for(key):
            await admin_service.require(session, user.tg_id, permission)
        if current:
            # Stale menu buttons cannot escape data-entry mode or execute hidden actions.
            await message.answer(t("input_controls"), reply_markup=reply.input_menu())
            return True
        await ACTIONS[entry.action](ctx)
        return True
    if current == ANSWER_STATE:
        await user_service.answers(message, state, session, bot, redis, user)
        if not (await state.get_data()).get("pending_action"):
            await state.set_state(None)
            await show(message, state, session, user, "user")
        return True
    return False
