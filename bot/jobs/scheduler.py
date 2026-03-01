"""Phase 2: APScheduler setup with minute-by-minute check.

In Phase 1, the scheduler is initialized but no jobs are registered yet.
Phase 2 activates morning briefs, evening reviews, and the reminder engine.
"""
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)

_scheduler = AsyncIOScheduler(timezone="Europe/Berlin")


def setup_scheduler() -> AsyncIOScheduler:
    """Initialize the scheduler. Jobs are added in Phase 2.

    Phase 2 will add:
    - check_all_jobs() every minute
    - Morning briefs per user setting
    - Evening reviews per user setting
    - Reminder engine processing
    - Weekly reflection trigger (Phase 3)
    """
    logger.info("Scheduler initialized (Phase 1: no jobs registered yet)")
    return _scheduler


# Phase 2 stubs:
# async def start_scheduler(): ...
# async def stop_scheduler(): ...
# async def check_all_jobs():
#     """Runs every minute. Checks each user for due briefs/reviews/reminders."""
#     ...
