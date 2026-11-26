"""Thin my_results Telegram adapter."""
from app.services.application_service import message as process


async def handle(message,state,session,bot,redis,user,is_new) -> None:
    """Delegate validation and domain work to application services."""
    await process(message,state,session,bot,redis,user,is_new)
