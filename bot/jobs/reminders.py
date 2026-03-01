"""Routine reminder job — checks routines and sends reminders."""
import logging
from datetime import date, datetime

from croniter import croniter
from sqlalchemy import and_, select

from bot.database.connection import get_session
from bot.database.models import Routine, RoutineCompletion, User
from bot.telegram.sender import send_message

logger = logging.getLogger(__name__)


async def send_routine_reminders() -> None:
    """Check all active routines and send reminders if due and not completed."""
    now = datetime.now()
    today_start = datetime.combine(date.today(), datetime.min.time())

    logger.info("Checking routine reminders at %s", now.strftime("%H:%M"))

    async with get_session() as session:
        result = await session.execute(
            select(Routine).where(Routine.status == "active")
        )
        routines = result.scalars().all()

        for routine in routines:
            try:
                # Check if cron matches current hour (within last 60 minutes)
                cron = croniter(routine.schedule_cron, now)
                prev_run = cron.get_prev(datetime)
                minutes_since = (now - prev_run).total_seconds() / 60

                if minutes_since > 60:
                    continue  # Not due in the last hour

                # Check if already completed today
                comp_result = await session.execute(
                    select(RoutineCompletion).where(
                        and_(
                            RoutineCompletion.routine_id == routine.id,
                            RoutineCompletion.completed_at >= today_start,
                        )
                    )
                )
                completion = comp_result.scalar_one_or_none()
                if completion:
                    continue  # Already done

                # Get user
                user_result = await session.execute(
                    select(User).where(User.id == routine.user_id)
                )
                user = user_result.scalar_one_or_none()
                if not user:
                    continue

                await send_message(
                    user.telegram_id,
                    f"⏰ Routine-Reminder: *{routine.title}*\n"
                    f"({routine.frequency_human})\n\n"
                    f"Schon erledigt? Antwort: 'Routine {routine.id} erledigt'",
                )
                logger.info("Reminder sent for routine %s to user %s", routine.id, user.id)
            except Exception as e:
                logger.exception("Reminder check failed for routine %s: %s", routine.id, e)
