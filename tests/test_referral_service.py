"""Invitation attribution and invalidation."""

from app.db.models import User
from app.services.referral_service import attribute, count, validate


async def test_attribution(db):
    inviter = User(tg_id=1, full_name="Inviter")
    invited = User(tg_id=2, full_name="Invited")
    db.add_all([inviter, invited])
    await db.flush()
    assert not await attribute(db, invited, 2, True)
    assert not await attribute(db, invited, 1, False)
    assert not await attribute(db, invited, 999, True)
    assert await attribute(db, invited, 1, True)
    assert not await attribute(db, invited, 1, True)
    assert await count(db, inviter.id) == 0
    assert not await validate(db, invited, False)
    invited.is_subscribed = True
    assert await validate(db, invited, True)
    assert not await validate(db, invited, True)
    assert await count(db, inviter.id) == 1
    await validate(db, invited, False)
    assert await count(db, inviter.id) == 0
    assert not await validate(db, inviter, True)
