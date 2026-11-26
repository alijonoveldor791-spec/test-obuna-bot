"""Administrator bootstrap, permissions and channel management."""

from aiogram import Bot
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import Admin, Channel
from app.services.errors import BusinessError
from app.texts import t

PERMISSIONS = {
    "owner": {"tests", "stats", "channels", "users", "admins", "settings", "broadcast", "exports"},
    "admin": {"tests", "stats", "channels", "users", "broadcast", "exports"},
    "moderator": {"stats", "exports"},
}


async def seed(session: AsyncSession) -> None:
    """Initialize configured administrators without overwriting DB roles."""
    for index, tg_id in enumerate(settings.admins):
        if not await session.scalar(select(Admin).where(Admin.tg_id == tg_id)):
            session.add(Admin(tg_id=tg_id, role="owner" if index == 0 else "admin"))
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


async def channel_command(session: AsyncSession, bot: Bot, value: str) -> None:
    """Add, remove or update required/main channel flags."""
    parts = value.split()
    if parts[0] in ("del", "required", "main"):
        channel = await session.get(Channel, int(parts[1]))
        if channel is None:
            raise BusinessError(t("invalid"))
        if parts[0] == "del":
            await session.delete(channel)
        elif parts[0] == "required":
            if parts[2] not in ("0", "1"):
                raise BusinessError(t("invalid"))
            channel.is_required = parts[2] == "1"
        else:
            for row in (await session.scalars(select(Channel))).all():
                row.is_main = row.id == channel.id
    else:
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
        row = await session.scalar(select(Channel).where(Channel.tg_chat_id == chat.id))
        if row is None:
            row = Channel(tg_chat_id=chat.id, title=chat.title or str(chat.id))
            session.add(row)
        row.username, row.invite_link = chat.username, link
        row.is_main = not bool(
            await session.scalar(select(Channel.id).where(Channel.is_main.is_(True)))
        )
    await session.flush()
