"""Persistent menu navigation and authorized reply-button actions."""

from types import SimpleNamespace
from typing import Any

from aiogram import Bot
from aiogram.fsm.context import FSMContext
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Admin, Channel, Test, User
from app.keyboards import reply
from app.services import admin_service, admin_ui_service, settings_service, user_service
from app.services import test_creation_service as creation
from app.services.errors import BusinessError
from app.states.add_test import AddTest
from app.states.broadcast import BroadcastInput
from app.texts import t

INPUT_STATE = "Navigation:input"
ANSWER_STATE = "Navigation:answers"


def button_key(text: str) -> str | None:
    """Resolve centralized translated labels, including setting indicators."""
    keys = (
        set(reply.ADMIN_KEYS)
        | set().union(*map(set, reply.SECTIONS.values()))
        | {
            "home",
            "back",
            "cancel_input",
            "submit_btn",
            "latest",
            "results",
            "referral",
            "help_btn",
        }
    )
    return next(
        (
            key
            for key in keys
            for lang in ("uz", "ru")
            if text == t(key, lang) or text in (t(key, lang) + ": ✅", t(key, lang) + ": ❌")
        ),
        None,
    )


async def show(
    message: Any,
    state: FSMContext,
    session: AsyncSession,
    user: User,
    destination: str | None = None,
) -> None:
    """Display a menu and save its parent path in Redis-backed FSM data."""
    data = await state.get_data()
    current_role = await admin_service.role(session, user.tg_id)
    destination = destination or data.get("nav_menu") or ("admin" if current_role else "user")
    if destination != "user" and not destination.startswith("user_") and not current_role:
        destination = "user"
    await state.update_data(nav_menu=destination)
    if destination == "user":
        keyboard = reply.user_menu(user.lang)
    elif destination.startswith("user_"):
        keyboard = reply.build([], user.lang, footer=True)
    elif destination == "admin":
        keyboard = reply.admin_menu(current_role, user.lang)
    else:
        await admin_service.require(session, user.tg_id, reply.permission(destination))
        keyboard = reply.section_menu(destination, user.lang)
        if destination == "settings":
            mapping = {
                "protect_btn": "protect_content",
                "reminders_btn": "reminders",
                "key_btn": "show_key_after_close",
            }
            for row in keyboard.keyboard:
                for button in row:
                    for key, setting in mapping.items():
                        if button.text == t(key, user.lang):
                            button.text += (
                                ": ✅" if await settings_service.get(session, setting) else ": ❌"
                            )
    await message.answer(
        t("admin_menu" if destination == "admin" else "nav_prompt", user.lang),
        reply_markup=keyboard,
    )


async def ask(message: Any, state: FSMContext, action: str, prompt: str, user: User) -> None:
    """Collect a single input while preserving its parent section."""
    await state.set_state(INPUT_STATE)
    await state.update_data(nav_action=action)
    await message.answer(t(prompt, user.lang), reply_markup=reply.input_menu(user.lang))


async def choose_test(
    message: Any, state: FSMContext, session: AsyncSession, user: User, action: str, page: int = 0
) -> None:
    """Show a paged inline test selector for an existing card/report operation."""
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    permission = (
        "exports"
        if action.startswith("export_")
        else "tests"
        if action in ("winners", "announce")
        else "stats"
    )
    await admin_service.require(session, user.tg_id, permission)
    rows = list(
        (
            await session.scalars(select(Test).order_by(Test.id.desc()).offset(page * 10).limit(11))
        ).all()
    )
    keyboard = [
        [
            InlineKeyboardButton(
                text=f"{row.code}: {row.title}"[:64], callback_data=f"nav:pick:{action}:{row.id}"
            )
        ]
        for row in rows[:10]
    ]
    pages = []
    if page:
        pages.append(
            InlineKeyboardButton(
                text=t("previous_page"), callback_data=f"nav:page:{action}:{page - 1}"
            )
        )
    if len(rows) > 10:
        pages.append(
            InlineKeyboardButton(text=t("next_page"), callback_data=f"nav:page:{action}:{page + 1}")
        )
    if pages:
        keyboard.append(pages)
    await message.answer(
        t("choose_test") if rows else t("empty"),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard) if keyboard else None,
    )


async def picked(
    message: Any,
    state: FSMContext,
    session: AsyncSession,
    bot: Bot,
    user: User,
    action: str,
    test_id: int,
) -> None:
    """Run the selected authorized report/card operation."""
    if action.startswith("export_"):
        await admin_ui_service.export(message, session, user, action[7:], test_id)
    else:
        if action in ("top10", "top50"):
            from app.services.ranking_service import recalculate

            await admin_service.require(session, user.tg_id, "stats")
            rows = await recalculate(session, test_id)
            lines = []
            for row in rows[: 10 if action == "top10" else 50]:
                person = await session.get(User, row.user_id)
                lines.append(
                    t("rank_row", rank=row.rank, name=person.full_name, percent=row.score_percent)
                )
            await message.answer("\n".join(lines) or t("empty"), parse_mode=None)
        else:
            await admin_ui_service.test_action(
                SimpleNamespace(message=message), state, session, bot, user, action, test_id
            )


async def handle(
    message: Any, state: FSMContext, session: AsyncSession, bot: Bot, redis: Redis, user: User
) -> bool:
    """Handle navigation before business FSM input, enforcing live roles."""
    text = message.text or ""
    if text.startswith("/") and text != "/cancel":
        return False
    key = button_key(text)
    current = await state.get_state()
    data = await state.get_data()
    parent = data.get(
        "nav_menu", "admin" if await admin_service.role(session, user.tg_id) else "user"
    )
    if key in ("home", "back", "cancel_input") or text == "/cancel":
        if key == "back" and current == AddTest.fields.state and data.get("field_index", 0) > 0:
            previous = data["field_index"] - 1
            if creation.FIELDS[previous] == "referral_count" and not data["draft"].get(
                "referral_required"
            ):
                previous -= 1
            await state.update_data(field_index=previous)
            await creation.prompt(message, state, session)
            return True
        if key == "back" and current == AddTest.fields.state:
            await state.set_state(AddTest.pdf)
            await message.answer(t("prompt_pdf"), reply_markup=reply.input_menu(user.lang))
            return True
        if key == "back" and current in (
            AddTest.confirm.state,
            BroadcastInput.button.state,
            BroadcastInput.confirm.state,
        ):
            if current == AddTest.confirm.state:
                await state.update_data(field_index=len(creation.FIELDS) - 1)
                await state.set_state(AddTest.fields)
                await creation.prompt(message, state, session)
            else:
                await state.set_state(
                    BroadcastInput.content
                    if current == BroadcastInput.button.state
                    else BroadcastInput.button
                )
                await message.answer(
                    t(
                        "broadcast_text"
                        if current == BroadcastInput.button.state
                        else "broadcast_button"
                    ),
                    reply_markup=reply.input_menu(user.lang),
                )
            return True
        await state.clear()
        destination = (
            parent
            if current or key == "cancel_input"
            else "user"
            if parent.startswith("user")
            else "admin"
        )
        if key == "home":
            destination = "admin" if await admin_service.role(session, user.tg_id) else "user"
        await show(message, state, session, user, destination)
        return True
    if current == INPUT_STATE:
        await input_value(message, state, session, bot, user, data)
        return True
    if current == ANSWER_STATE:
        await user_service.answers(message, state, session, bot, redis, user)
        await state.set_state(None)
        await show(message, state, session, user, "user")
        return True
    if current:
        return False
    if key in reply.ADMIN_KEYS and key != "user_mode":
        await admin_service.require(session, user.tg_id, reply.permission(key))
        if key == "new_test":
            await creation.start(message, state)
            await state.update_data(nav_menu="tests")
        else:
            await show(message, state, session, user, key)
        return True
    if key == "user_mode":
        await show(message, state, session, user, "user")
        return True
    if key in ("submit_btn", "help_btn"):
        if key == "submit_btn":
            await state.set_state(ANSWER_STATE)
        await state.update_data(nav_menu="user" if key == "submit_btn" else "user_help")
        await message.answer(
            t("answer_prompt" if key == "submit_btn" else "help", user.lang),
            reply_markup=reply.input_menu(user.lang)
            if key == "submit_btn"
            else reply.build([], user.lang, footer=True),
        )
        return True
    if key in ("latest", "results", "referral"):
        await show(message, state, session, user, "user_" + key)
        if key == "latest":
            await user_service.send_test(message, state, session, bot, redis, user)
        elif key == "results":
            await user_service.my_results(message, session, user)
        else:
            await user_service.referral(message, session, user)
        return True
    section = next((section for section, keys in reply.SECTIONS.items() if key in keys), None)
    if not section:
        return False
    await admin_service.require(session, user.tg_id, reply.permission(section))
    await state.update_data(nav_menu=section)
    if key in ("active", "draft", "closed"):
        await admin_ui_service.list_tests(message, session, user, key)
    elif key in ("general", "growth", "ref_top"):
        from app.repositories.stats import general

        await message.answer(t("general_stats", **await general(session)), parse_mode=None)
    elif key in ("export_users", "export_refs"):
        await admin_ui_service.export(message, session, user, key[7:], 0)
    elif key in (
        "test_stats_btn",
        "top10",
        "top50",
        "winners_btn",
        "publish_results_btn",
        "export_results",
        "export_access",
    ):
        await choose_test(
            message,
            state,
            session,
            user,
            {
                "test_stats_btn": "stats",
                "winners_btn": "winners",
                "publish_results_btn": "winners",
            }.get(key, key),
        )
    elif key in ("list_channels", "list_admins", "banned_btn"):
        model = {"list_channels": Channel, "list_admins": Admin, "banned_btn": User}[key]
        query = select(model).limit(50)
        if model is User:
            query = query.where(User.is_banned.is_(True))
        rows = (await session.scalars(query)).all()
        await message.answer(
            "\n".join(
                f"{row.id}: {getattr(row, 'title', getattr(row, 'tg_id', ''))}" for row in rows
            )
            or t("empty")
        )
    elif key in ("protect_btn", "reminders_btn", "key_btn"):
        setting = {
            "protect_btn": "protect_content",
            "reminders_btn": "reminders",
            "key_btn": "show_key_after_close",
        }[key]
        await settings_service.set_value(
            session, setting, not await settings_service.get(session, setting)
        )
        await show(message, state, session, user, section)
    elif key in ("all_btn", "left_btn"):
        await state.update_data(
            broadcast={"audience": "all" if key == "all_btn" else "left", "test_id": None}
        )
        await state.set_state(BroadcastInput.content)
        await message.answer(t("broadcast_text"), reply_markup=reply.input_menu(user.lang))
    else:
        await ask(
            message,
            state,
            key,
            "enter_code"
            if key == "search_code"
            else "enter_language"
            if key == "language_btn"
            else "enter_number"
            if key == "ref_default"
            else "enter_test"
            if key in ("participants_btn", "pending_btn")
            else "enter_id",
            user,
        )
    return True


async def input_value(
    message: Any, state: FSMContext, session: AsyncSession, bot: Bot, user: User, data: dict
) -> None:
    """Translate simple user input into existing permission-checked service calls."""
    action = data["nav_action"]
    parent = data["nav_menu"]
    await admin_service.require(session, user.tg_id, reply.permission(parent))
    value = (message.text or "").strip()
    if action == "search_code":
        test = await session.scalar(
            select(Test)
            .where(Test.code == value)
            .order_by((Test.status == "active").desc(), Test.id.desc())
            .limit(1)
        )
        if not test:
            raise BusinessError(t("no_test"))
        await admin_ui_service.card(message, session, user, test.id)
    elif action in ("ref_default", "language_btn"):
        await settings_service.set_value(
            session,
            "referral_default" if action == "ref_default" else "language",
            int(value) if action == "ref_default" else value,
        )
    elif action in ("participants_btn", "pending_btn"):
        if not await session.get(Test, int(value)):
            raise BusinessError(t("no_test"))
        await state.update_data(
            broadcast={
                "audience": "participants" if action == "participants_btn" else "pending",
                "test_id": int(value),
            }
        )
        await state.set_state(BroadcastInput.content)
        await message.answer(t("broadcast_text"), reply_markup=reply.input_menu(user.lang))
        return
    else:
        prefix = {
            "ban_btn": "ban ",
            "unban_btn": "unban ",
            "del_channel": "del ",
            "del_admin": "del ",
        }.get(action, "")
        if action == "add_admin" and len(value.split()) == 1:
            value += " admin"
        await state.update_data(section=parent)
        await admin_ui_service.input_value(
            SimpleNamespace(text=prefix + value, answer=message.answer), state, session, bot, user
        )
    await state.set_state(None)
    await show(message, state, session, user, parent)
