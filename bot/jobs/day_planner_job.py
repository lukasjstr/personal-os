"""Daily job: generate time-blocked day schedule at 06:00."""
import logging

from sqlalchemy import select

from bot.database.connection import get_session
from bot.database.models import User

logger = logging.getLogger(__name__)


async def run_day_planner() -> None:
    """06:00 daily: generate time-blocked CalendarEvent schedule for each active user."""
    from bot.core.day_scheduler import generate_day_schedule

    async with get_session() as session:
        result = await session.execute(select(User).where(User.is_active == True))  # noqa: E712
        users = result.scalars().all()

        for user in users:
            try:
                schedule, daily_focus = await generate_day_schedule(session, user)
                await session.commit()
                logger.info(
                    "Day planner: scheduled %d blocks for user %d (focus: %s)",
                    len(schedule), user.id, daily_focus[:60] if daily_focus else "-",
                )
            except Exception:
                logger.exception("Day planner failed for user %d", user.id)
