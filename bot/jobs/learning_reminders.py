"""09:30 daily: notify users of items due for spaced repetition review."""
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.connection import get_session
from bot.database.models import User
from bot.core.knowledge import get_due_reviews
from bot.telegram.sender import send_message

logger = logging.getLogger(__name__)


async def send_learning_reminders() -> None:
    """09:30 daily: notify users of items due for spaced repetition review."""
    async with get_session() as session:
        result = await session.execute(
            select(User).where(User.is_active == True)  # noqa: E712
        )
        users = result.scalars().all()

        for user in users:
            try:
                due_items = await get_due_reviews(session, user.id)
                if not due_items:
                    continue

                count = len(due_items)
                items_preview = ", ".join(item.title for item in due_items[:3])
                if count > 3:
                    items_preview += f" +{count - 3} weitere"

                msg = (
                    f"📚 *{count} Lernkarte{'n' if count > 1 else ''} zur Wiederholung fällig*\n"
                    f"{items_preview}\n\n"
                    f"Nutze /learn zum Starten."
                )
                await send_message(user.telegram_id, msg)
                logger.info("Learning reminder sent to user %s (%d due items)", user.id, count)
            except Exception:
                logger.exception("Learning reminder failed for user %s", user.id)
