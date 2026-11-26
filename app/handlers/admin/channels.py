"""Thin channels Telegram adapter."""
from app.services.application_service import callback as process


async def handle(callback,state,session,bot,redis,user) -> None:
    """Delegate validation and domain work to application services."""
    await process(callback,state,session,bot,redis,user)
