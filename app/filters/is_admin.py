"""Administrator filter backed by live DB permissions."""

from aiogram.filters import Filter

from app.services.admin_service import role


class IsAdmin(Filter):
    """Accept existing administrators."""

    async def __call__(self, event, session) -> bool:
        return bool(await role(session, event.from_user.id))
