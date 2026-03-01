"""APScheduler setup and job registration."""
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from bot.jobs.morning_brief import send_morning_brief
from bot.jobs.evening_review import send_evening_review
from bot.jobs.reminders import send_routine_reminders

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone="Europe/Berlin")


def setup_scheduler() -> AsyncIOScheduler:
    """Register all cron jobs and return the scheduler."""

    # Morning brief at 06:30 every day
    scheduler.add_job(
        send_morning_brief,
        CronTrigger(hour=6, minute=30, timezone="Europe/Berlin"),
        id="morning_brief",
        replace_existing=True,
        name="Morning Brief",
    )

    # Evening review at 21:00 every day
    scheduler.add_job(
        send_evening_review,
        CronTrigger(hour=21, minute=0, timezone="Europe/Berlin"),
        id="evening_review",
        replace_existing=True,
        name="Evening Review",
    )

    # Check routine reminders every hour
    scheduler.add_job(
        send_routine_reminders,
        CronTrigger(minute=0, timezone="Europe/Berlin"),
        id="routine_reminders",
        replace_existing=True,
        name="Routine Reminders",
    )

    logger.info("Scheduler configured with %d jobs", len(scheduler.get_jobs()))
    return scheduler
