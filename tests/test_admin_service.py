"""Role restrictions and channel validation."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.db.models import Admin, Channel
from app.services.admin_service import channel_command, require, seed


async def test_roles(db):
    await seed(db)
    db.add(Admin(tg_id=77, role="moderator"))
    await db.flush()
    assert await require(db, 77, "stats") == "moderator"
    with pytest.raises(PermissionError):
        await require(db, 77, "tests")
    with pytest.raises(PermissionError):
        await require(db, 99, "stats")


async def test_channel(db):
    bot = SimpleNamespace(
        get_chat=AsyncMock(
            return_value=SimpleNamespace(
                id=-1001, type="channel", title="Title", username="title", invite_link=None
            )
        ),
        get_me=AsyncMock(return_value=SimpleNamespace(id=1)),
        get_chat_member=AsyncMock(
            return_value=SimpleNamespace(status="administrator", can_post_messages=True)
        ),
    )
    await channel_command(db, bot, "@title")
    from sqlalchemy import select

    channel = await db.scalar(select(Channel))
    assert channel.is_required and channel.is_main
    await channel_command(db, bot, f"required {channel.id} 0")
    assert not channel.is_required
    bot.get_chat_member.return_value.status = "member"
    with pytest.raises(ValueError):
        await channel_command(db, bot, "@bad")
    await channel_command(db, bot, f"del {channel.id}")
