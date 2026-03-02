"""Phase 4: APScheduler setup with all proactive jobs active."""
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from bot.jobs.evening_review import send_evening_review
from bot.jobs.morning_brief import send_morning_brief
from bot.jobs.reminders import process_reminders
from bot.jobs.weekly_reflection_trigger import check_and_trigger_reflections

logger = logging.getLogger(__name__)

_scheduler = AsyncIOScheduler(timezone="Europe/Berlin")


def setup_scheduler() -> AsyncIOScheduler:
    """Initialize scheduler with all Phase 4 jobs.

    Jobs:
    - Every minute: check if any user's morning brief or evening review time matches now
    - Every 30 minutes: process proactive reminders (calendar, overdue, routines, nudges)
    - Every minute (Sundays only): check if any user's weekly reflection time matches now
    """
    # Morning and evening briefs: run every minute, each function checks timing internally
    _scheduler.add_job(
        send_morning_brief,
        "interval",
        minutes=1,
        id="morning_brief",
        max_instances=1,
        coalesce=True,
    )
    _scheduler.add_job(
        send_evening_review,
        "interval",
        minutes=1,
        id="evening_review",
        max_instances=1,
        coalesce=True,
    )

    # Proactive reminders: every 30 minutes
    _scheduler.add_job(
        process_reminders,
        "interval",
        minutes=30,
        id="reminders",
        max_instances=1,
        coalesce=True,
    )

    # Weekly reflection: every minute (function checks if it's Sunday internally)
    _scheduler.add_job(
        check_and_trigger_reflections,
        "interval",
        minutes=1,
        id="weekly_reflection",
        max_instances=1,
        coalesce=True,
    )

    logger.info("Scheduler initialized with 4 active jobs: morning_brief, evening_review, reminders, weekly_reflection")
    return _scheduler
