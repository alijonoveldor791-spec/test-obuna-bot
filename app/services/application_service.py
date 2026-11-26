"""Route conversations to domain services."""

from app.services import admin_ui_service as admin_ui
from app.services import broadcast_ui_service as broadcast_ui
from app.services import nav_service as nav
from app.services import test_creation_service as creation
from app.services import user_service as users
from app.services.admin_service import require, role
from app.services.errors import BusinessError
from app.states.add_test import AddTest
from app.states.admin_misc import AdminInput
from app.states.broadcast import BroadcastInput
from app.texts import t


async def message(message, state, session, bot, redis, user, is_new) -> None:
    """Dispatch a private message without embedding logic in handlers."""
    text = message.text or ""
    command = text.split(maxsplit=1)[0].split("@")[0] if text else ""
    current = await state.get_state()
    if await nav.handle(message, state, session, bot, redis, user):
        return
    if command == "/cancel":
        await state.clear()
        await message.answer(t("cancelled", user.lang))
    elif command == "/admin":
        await state.clear()
        await nav.show(message, state, session, user, "admin")
    elif command == "/start":
        await state.clear()
        if await role(session, user.tg_id):
            await nav.show(message, state, session, user, "admin")
        else:
            await state.update_data(nav_menu="user")
            await users.start(message, state, session, bot, redis, user, is_new)
    elif command == "/help":
        await message.answer(t("help", user.lang))
    elif command == "/language":
        lang = text.split()[-1]
        if lang not in ("uz", "ru"):
            raise BusinessError(t("invalid"))
        user.lang = lang
        from app.keyboards.user import menu

        if await role(session, user.tg_id):
            await nav.show(message, state, session, user, "admin")
        else:
            await message.answer(t("language_saved", lang), reply_markup=menu(lang))
    elif current == AddTest.pdf.state:
        await require(session, user.tg_id, "tests")
        await creation.receive_pdf(message, state, session, bot)
    elif current == AddTest.fields.state:
        await require(session, user.tg_id, "tests")
        await creation.field_value(message, state, session)
    elif current == AdminInput.value.state:
        parent = (await state.get_data()).get("nav_menu", "tests")
        await admin_ui.input_value(message, state, session, bot, user)
        await nav.show(message, state, session, user, parent)
    elif current == BroadcastInput.audience.state:
        await broadcast_ui.audience(message, state, session, user)
    elif current == BroadcastInput.content.state:
        await broadcast_ui.content(message, state, session, user)
    elif current == BroadcastInput.button.state:
        await broadcast_ui.button(message, state, session, user)
    elif current in (AddTest.confirm.state, BroadcastInput.confirm.state):
        await message.answer(t("confirm", user.lang))
    elif command == "/test" or text in (t("latest", "uz"), t("latest", "ru")):
        await users.send_test(message, state, session, bot, redis, user)
    elif command == "/results" or text in (t("results", "uz"), t("results", "ru")):
        await users.my_results(message, session, user)
    elif command == "/referral" or text in (t("referral", "uz"), t("referral", "ru")):
        await users.referral(message, session, user)
    elif text and not text.startswith("/"):
        import re

        if re.match(r"^(?:[0-9]|[a-dA-D]+$)", text):
            await users.answers(message, state, session, bot, redis, user)
        else:
            await nav.show(message, state, session, user)
    else:
        await nav.show(message, state, session, user)


async def callback(callback, state, session, bot, redis, user) -> None:
    """Dispatch callback actions with service-level permission checks."""
    parts = (callback.data or "").split(":")
    prefix = parts[0]
    await callback.answer()
    if prefix == "nav":
        if parts[1] == "page":
            await nav.choose_test(callback.message, state, session, user, parts[2], int(parts[3]))
        else:
            await nav.picked(callback.message, state, session, bot, user, parts[2], int(parts[3]))
    elif prefix == "sub" and parts[1] == "check":
        await users.resume(callback, state, session, bot, redis, user)
    elif prefix == "ref":
        await users.referral(callback.message, session, user)
    elif prefix == "adm":
        await nav.show(callback.message, state, session, user, parts[1])
    elif prefix == "list":
        await admin_ui.list_tests(callback.message, session, user, parts[1], int(parts[2]))
    elif prefix == "new":
        await require(session, user.tg_id, "tests")
        if parts[1] == "start":
            await creation.start(callback.message, state)
        elif parts[1] in ("publish", "schedule", "send_me"):
            test_id = await creation.confirm(callback, state, session)
            await state.update_data(nav_menu="tests")
            await nav.show(callback.message, state, session, user, "tests")
            await admin_ui.test_action(callback, state, session, bot, user, parts[1], test_id)
        elif parts[1] == "confirm":
            test_id = await creation.confirm(callback, state, session)
            await admin_ui.card(callback.message, session, user, test_id)
        elif parts[1] == "edit":
            await state.update_data(field_index=0)
            await state.set_state(AddTest.fields)
            await creation.prompt(callback.message, state, session)
        elif parts[1] == "cancel":
            data = await state.get_data()
            await state.clear()
            await nav.show(callback.message, state, session, user, data.get("nav_menu", "admin"))
    elif prefix == "t":
        await admin_ui.test_action(callback, state, session, bot, user, parts[1], int(parts[2]))
    elif prefix == "exp":
        await admin_ui.export(callback.message, session, user, parts[1], int(parts[2]))
    elif prefix == "bc":
        await broadcast_ui.action(callback, state, session, user, parts[1], int(parts[2]))
        if await state.get_state() is None:
            await nav.show(callback.message, state, session, user, "broadcast")
    else:
        raise BusinessError(t("invalid"))
