"""Business orchestration for administrator interactions."""

import json

from aiogram.types import BufferedInputFile
from sqlalchemy import delete, func, select

from app.db.models import Admin, Channel, Submission, Test, User
from app.keyboards.admin import buttons, test_card
from app.keyboards.reply import admin_menu, input_menu
from app.repositories import stats
from app.services import (
    admin_service,
    export_service,
    grading_service,
    post_service,
    ranking_service,
    referral_service,
    settings_service,
    test_creation_service,
)
from app.services.errors import BusinessError
from app.states.admin_misc import AdminInput
from app.states.broadcast import BroadcastInput
from app.texts import t


async def home(message, session, user) -> None:
    """Display permitted administrator sections."""
    role = await admin_service.role(session, user.tg_id)
    if not role:
        raise PermissionError(t("denied"))
    await message.answer(t("admin_menu", user.lang), reply_markup=admin_menu(role, user.lang))


async def card(message, session, user, test_id: int) -> None:
    """Show one test and allowed actions."""
    role = await admin_service.require(session, user.tg_id, "stats")
    test = await session.get(Test, test_id)
    if test is None:
        raise BusinessError(t("no_test"))
    await message.answer(
        t(
            "card",
            title=test.title,
            code=test.code,
            status=test.status,
            questions=test.questions_count,
            deadline=test.end_at or t("unlimited"),
        ),
        reply_markup=test_card(test.id, role),
        parse_mode=None,
    )


async def list_tests(message, session, user, status="active", page=0) -> None:
    """Page tests by lifecycle status."""
    await admin_service.require(session, user.tg_id, "stats")
    if status not in ("active", "draft", "paused", "closed") or page < 0:
        raise BusinessError(t("invalid"))
    tests = (
        await session.scalars(
            select(Test)
            .where(Test.status == status)
            .order_by(Test.id.desc())
            .offset(page * 10)
            .limit(11)
        )
    ).all()
    items = [(row.title[:48], f"t:view:{row.id}") for row in tests[:10]]
    # Custom titles are already data, not locale keys.
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    keyboard = [[InlineKeyboardButton(text=title, callback_data=data)] for title, data in items]
    keyboard += [
        [InlineKeyboardButton(text=s, callback_data=f"list:{s}:0")]
        for s in ("active", "draft", "paused", "closed")
    ]
    if page:
        keyboard.append(
            [InlineKeyboardButton(text=t("back"), callback_data=f"list:{status}:{page - 1}")]
        )
    if len(tests) > 10:
        keyboard.append(
            [InlineKeyboardButton(text=t("next"), callback_data=f"list:{status}:{page + 1}")]
        )

    await message.answer(t("tests"), reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))


async def section(message, state, session, bot, user, section: str) -> None:
    """Open an authorized menu section or input conversation."""
    await admin_service.require(session, user.tg_id, section)
    if section == "tests":
        await list_tests(message, session, user)
    elif section == "stats":
        await message.answer(t("general_stats", **await stats.general(session)), parse_mode=None)
    elif section == "exports":
        await message.answer(
            t("exports"),
            reply_markup=buttons([("export_users", "exp:users:0"), ("export_refs", "exp:refs:0")]),
        )
    elif section == "broadcast":
        await state.clear()
        await state.set_state(BroadcastInput.audience)
        await message.answer(t("broadcast_prompt"))
    else:
        await state.set_state(AdminInput.value)
        await state.update_data(section=section)
        if section == "channels":
            rows = (await session.scalars(select(Channel).order_by(Channel.id))).all()
            await message.answer(
                "\n".join(
                    f"{r.id}: {r.title} ({r.tg_chat_id}) required={r.is_required}, main={r.is_main}"
                    for r in rows
                )
                or t("empty"),
                parse_mode=None,
            )
        if section == "admins":
            rows = (await session.scalars(select(Admin))).all()
            await message.answer("\n".join(f"{r.tg_id}: {r.role}" for r in rows) or t("empty"))
        values = {
            key: await settings_service.get(session, key) for key in settings_service.DEFAULTS
        }
        await message.answer(
            t(
                {
                    "channels": "channel_prompt",
                    "users": "user_prompt",
                    "admins": "admin_prompt",
                    "settings": "settings_prompt",
                }[section],
                values=json.dumps(values, ensure_ascii=False),
            )
        )


async def input_value(message, state, session, bot, user) -> None:
    """Apply one permission-checked administrator edit."""
    data = await state.get_data()
    section = data["section"]
    await admin_service.require(session, user.tg_id, section)
    value = (message.text or "").strip()
    parts = value.split()
    if section == "channels":
        await admin_service.channel_command(session, bot, value)
    elif section == "settings":
        key, raw = value.split(maxsplit=1)
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = raw
        await settings_service.set_value(session, key, parsed)
    elif section == "admins":
        removing = parts[0] == "del"
        tg_id = int(parts[1] if removing else parts[0])
        if tg_id == user.tg_id or (
            tg_id in __import__("app.config", fromlist=["settings"]).settings.admins
        ):
            raise BusinessError(t("denied"))
        row = await session.scalar(select(Admin).where(Admin.tg_id == tg_id).with_for_update())
        if removing:
            if row:
                await session.delete(row)
        else:
            if parts[1] not in admin_service.PERMISSIONS:
                raise BusinessError(t("invalid"))
            if row:
                row.role = parts[1]
            else:
                session.add(Admin(tg_id=tg_id, role=parts[1], added_by=user.tg_id))
    elif section == "users":
        action = parts[0] if parts[0] in ("ban", "unban") else "find"
        target = parts[1] if action != "find" else parts[0]
        query = (
            select(User).where(User.tg_id == int(target))
            if target.isdigit()
            else select(User).where(User.username == target.lstrip("@"))
        )
        found = await session.scalar(query.with_for_update())
        if found is None:
            raise BusinessError(t("empty"))
        if action != "find":
            if await admin_service.role(session, found.tg_id):
                raise BusinessError(t("denied"))
            found.is_banned = action == "ban"
        result_count = await session.scalar(
            select(func.count()).select_from(Submission).where(Submission.user_id == found.id)
        )
        await message.answer(
            t(
                "user_card",
                name=found.full_name,
                username=found.username or "?",
                tg_id=found.tg_id,
                banned=found.is_banned,
                results=result_count,
                refs=await referral_service.count(session, found.id),
            ),
            parse_mode=None,
        )
    elif section == "tests":
        test_id, action = data["test_id"], data["action"]
        test = await session.scalar(select(Test).where(Test.id == test_id).with_for_update())
        if action == "key":
            await grading_service.change_key(session, test_id, value)
        elif action == "description":
            if len(value) > 1000:
                raise BusinessError(t("invalid"))
            test.description = value
        elif action == "deadline":
            test.end_at = test_creation_service.parse_date(value)
        elif action == "schedule":
            scheduled = test_creation_service.parse_date(value)
            if scheduled is None or test.status == "closed":
                raise BusinessError(t("invalid"))
            test.scheduled_at = scheduled
    await session.flush()
    await state.clear()
    await message.answer(t("saved", user.lang))


async def test_action(callback, state, session, bot, user, action: str, test_id: int) -> None:
    """Execute lifecycle actions or collect a validated new value."""
    await admin_service.require(
        session,
        user.tg_id,
        "stats" if action in ("view", "ranking", "stats", "review") else "tests",
    )
    message = callback.message
    if action == "view":
        await card(message, session, user, test_id)
    elif action == "stats":
        test = await session.get(Test, test_id)
        await message.answer(t("test_stats", **await stats.for_test(session, test)))
    elif action in ("ranking", "review"):
        rows = await ranking_service.recalculate(session, test_id)
        text = []
        for row in rows[:50]:
            person = await session.get(User, row.user_id)
            text.append(
                t("rank_row", rank=row.rank, name=person.full_name, percent=row.score_percent)
            )
        await message.answer("\n".join(text) or t("empty"), parse_mode=None)
    elif action in ("publish", "send_me"):
        await post_service.publish(
            session, bot, test_id, user.tg_id if action == "send_me" else None
        )
        await message.answer(t("saved"))
    elif action == "close":
        await post_service.close(session, bot, test_id)
        await card(message, session, user, test_id)
    elif action == "winners":
        await test_action(callback, state, session, bot, user, "review", test_id)
        await message.answer(
            t("confirm"), reply_markup=buttons([("confirm", f"t:announce:{test_id}")])
        )
    elif action == "announce":
        await post_service.results(session, bot, test_id)
        await message.answer(t("saved"))
    elif action == "delete":
        await message.answer(
            t("delete_confirm"),
            reply_markup=buttons(
                [("confirm", f"t:delete_yes:{test_id}"), ("cancel", "new:cancel")]
            ),
        )
    elif action == "delete_yes":
        await session.execute(delete(Test).where(Test.id == test_id))
        await message.answer(t("saved"))
    elif action in ("pause", "resume"):
        test = await session.scalar(select(Test).where(Test.id == test_id).with_for_update())
        if test is None or test.status not in ("paused", "active"):
            raise BusinessError(t("invalid"))
        test.status = "paused" if action == "pause" else "active"
        await card(message, session, user, test_id)
    elif action in ("key", "description", "deadline", "schedule"):
        await state.set_state(AdminInput.value)
        await state.update_data(section="tests", test_id=test_id, action=action)
        await message.answer(t("prompt_change"), reply_markup=input_menu(user.lang))
    else:
        raise BusinessError(t("invalid"))


async def export(message, session, user, kind: str, test_id: int) -> None:
    """Send an authorized Excel report."""
    await admin_service.require(session, user.tg_id, "exports")
    content = await export_service.export(session, kind, test_id)
    await message.answer_document(BufferedInputFile(content, filename=f"{kind}-{test_id}.xlsx"))
