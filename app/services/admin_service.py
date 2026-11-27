"""Administrator bootstrap, permissions and channel management."""

from aiogram import Bot
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import Admin, Channel
from app.services.errors import BusinessError
from app.texts import t

PERMISSIONS = {
    "owner": {
        "panel",
        "tests_view",
        "tests",
        "stats",
        "channels",
        "users",
        "admins",
        "settings",
        "broadcast",
        "exports",
    },
    "admin": {"panel", "tests_view", "tests", "stats", "users", "broadcast", "exports"},
    "moderator": {"panel", "tests_view", "stats", "exports"},
}


async def seed(session: AsyncSession) -> None:
    """Initialize configured administrators without overwriting DB roles."""
    for index, tg_id in enumerate(settings.admins):
        if not await session.scalar(select(Admin).where(Admin.tg_id == tg_id)):
            session.add(Admin(tg_id=tg_id, role="owner" if index == 0 else "admin"))
    channels = list((await session.scalars(select(Channel).order_by(Channel.id))).all())
    main = next((row for row in channels if row.is_main), channels[0] if channels else None)
    for row in channels:
        row.is_required = True
        row.is_main = row is main
    await session.flush()


async def role(session: AsyncSession, tg_id: int) -> str | None:
    """Read live role, so revocations take effect immediately."""
    return await session.scalar(select(Admin.role).where(Admin.tg_id == tg_id))


async def require(session: AsyncSession, tg_id: int, permission: str) -> str:
    """Enforce authorization in service calls as well as UI."""
    current = await role(session, tg_id)
    if permission not in PERMISSIONS.get(current, set()):
        raise PermissionError(t("denied"))
    return current


async def add_channel(session: AsyncSession, bot: Bot, value: str) -> None:
    """Add a validated Telegram channel; every configured channel is required."""
    if (
        not (value.startswith("@") and value[1:].replace("_", "").isalnum())
        and not value.lstrip("-").isdigit()
    ):
        raise BusinessError(t("channel_target"))
    chat_id = int(value) if value.lstrip("-").isdigit() else value
    chat = await bot.get_chat(chat_id)
    me = await bot.get_me()
    member = await bot.get_chat_member(chat.id, me.id)
    if chat.type not in ("channel", "supergroup") or member.status not in (
        "administrator",
        "creator",
    ):
        raise BusinessError(t("channel_error"))
    if (
        member.status == "administrator"
        and chat.type == "channel"
        and not getattr(member, "can_post_messages", False)
    ):
        raise BusinessError(t("channel_error"))
    link = chat.invite_link
    if not chat.username and not link:
        link = (await bot.create_chat_invite_link(chat.id)).invite_link
    rows = list(
        (await session.scalars(select(Channel).order_by(Channel.id).with_for_update())).all()
    )
    row = next((row for row in rows if row.tg_chat_id == chat.id), None)
    if row is None:
        row = Channel(tg_chat_id=chat.id, title=chat.title or str(chat.id))
        session.add(row)
        rows.append(row)
    row.title, row.username, row.invite_link = chat.title or str(chat.id), chat.username, link
    main = next((candidate for candidate in rows if candidate.is_main), rows[0])
    for candidate in rows:
        candidate.is_required = True
        candidate.is_main = candidate is main
    await session.flush()


async def remove_channel(session: AsyncSession, channel_id: int) -> None:
    """Delete a channel and select the next primary channel deterministically."""
    rows = list(
        (await session.scalars(select(Channel).order_by(Channel.id).with_for_update())).all()
    )
    row = next((row for row in rows if row.id == channel_id), None)
    if row is None:
        raise BusinessError(t("empty"))
    await session.delete(row)
    remaining = [candidate for candidate in rows if candidate is not row]
    main = next(
        (candidate for candidate in remaining if candidate.is_main),
        remaining[0] if remaining else None,
    )
    for candidate in remaining:
        candidate.is_main = candidate is main
        candidate.is_required = True
    await session.flush()


async def channel_command(session: AsyncSession, bot: Bot, value: str) -> None:
    """Compatibility entry for startup channel registration; no command grammar."""
    await add_channel(session, bot, value)
