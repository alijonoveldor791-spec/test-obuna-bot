"""Compose private-chat adapters without business logic."""
from aiogram import F, Router
from aiogram.filters import Command, CommandStart

from app.filters.is_private import IsPrivate
from app.handlers.admin import (
    add_test,
    admins,
    broadcast,
    channels,
    export,
    menu,
    results,
    settings,
    stats,
    tests_manage,
    users,
)
from app.handlers.user import common, get_test, my_results, referral, start, submit_answers
from app.keyboards.reply import ADMIN_KEYS, SECTIONS
from app.texts import t


def build_router() -> Router:
    """Register command and callback adapters with a final conversation fallback."""
    router=Router()
    router.message.filter(IsPrivate())
    router.callback_query.filter(IsPrivate())
    router.message.register(start.handle,CommandStart())
    for command,module in (("admin",menu),("test",get_test),("results",my_results),("referral",referral)):
        router.message.register(module.handle,Command(command))
    router.message.register(common.handle,Command("help","cancel","language"))
    button_keys = set(ADMIN_KEYS) | set().union(*map(set, SECTIONS.values())) | {
        "back", "home", "cancel_input", "submit_btn", "help_btn", "latest", "results", "referral"}
    for key in button_keys:
        for lang in ("uz", "ru"):
            router.message.register(common.handle, F.text == t(key, lang))
    router.message.register(submit_answers.handle)
    for prefix,module in (("new:",add_test),("exp:",export),("bc:",broadcast),("sub:",tests_manage),("ref:",tests_manage),("res:",tests_manage),("rank:",results),("t:stats:",stats),("t:ranking:",results),("t:review:",results),("adm:admins",admins),("adm:broadcast",broadcast),("adm:channels",channels),("adm:exports",export),("adm:settings",settings),("adm:stats",stats),("adm:users",users)):
        router.callback_query.register(module.handle,F.data.startswith(prefix))
    router.callback_query.register(tests_manage.handle)
    return router
