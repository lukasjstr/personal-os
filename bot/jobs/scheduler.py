"""Phase 4: APScheduler setup with all proactive jobs active."""
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from bot.core.daily_intelligence import (
    run_evening_checkin,
    run_morning_context_collection,
    run_streak_risk_check,
)
from bot.jobs.daily_suggestions import generate_daily_suggestions
from bot.jobs.evening_review import send_evening_review
from bot.jobs.morning_brief import send_morning_brief
from bot.jobs.reminders import process_reminders
from bot.jobs.weekly_reflection_trigger import check_and_trigger_reflections
from bot.jobs.weekly_auto_plan import send_weekly_auto_plan
from bot.jobs.daily_prompts import send_journal_prompts, send_gratitude_prompts
from bot.jobs.day_planner_job import run_day_planner
from bot.jobs.post_event_followup import process_post_event_followups
from bot.jobs.pattern_analysis import run_weekly_pattern_analysis

logger = logging.getLogger(__name__)

_scheduler = AsyncIOScheduler(timezone="Europe/Berlin")


def setup_scheduler() -> AsyncIOScheduler:
    """Initialize scheduler with all jobs.

    Jobs:
    - 06:30 daily: generate daily AI suggestions (before morning brief)
    - 07:00 daily: send morning brief
    - 21:00 daily: send evening review
    - Every 30 minutes: process proactive reminders (calendar, overdue, routines, nudges)
    - 08:00 Sundays: check and trigger weekly reflections
    """
    # Daily AI suggestions at 06:30
    _scheduler.add_job(
        generate_daily_suggestions,
        CronTrigger(hour=6, minute=30, timezone="Europe/Berlin"),
        id="daily_suggestions",
        max_instances=1,
        coalesce=True,
    )

    # Morning brief at 07:00
    _scheduler.add_job(
        send_morning_brief,
        CronTrigger(hour=7, minute=0, timezone="Europe/Berlin"),
        id="morning_brief",
        max_instances=1,
        coalesce=True,
    )

    # Evening review at 20:45 (legacy summary before interactive check-in)
    _scheduler.add_job(
        send_evening_review,
        CronTrigger(hour=20, minute=45, timezone="Europe/Berlin"),
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

    # Weekly reflection: Sundays at 08:00
    _scheduler.add_job(
        check_and_trigger_reflections,
        CronTrigger(hour=8, minute=0, day_of_week="sun", timezone="Europe/Berlin"),
        id="weekly_reflection",
        max_instances=1,
        coalesce=True,
    )

    # iCal sync: every 15 minutes
    from bot.jobs.ical_sync import sync_all_users as ical_sync_all
    _scheduler.add_job(
        ical_sync_all,
        "interval",
        minutes=15,
        id="ical_sync",
        max_instances=1,
        coalesce=True,
    )

    # Gap nudge: every 30 minutes during active hours
    from bot.jobs.gap_nudge import send_gap_nudges
    _scheduler.add_job(
        send_gap_nudges,
        "interval",
        minutes=30,
        id="gap_nudge",
        max_instances=1,
        coalesce=True,
    )

    # Sprint 3: Weekly auto-plan on Mondays at 07:30
    _scheduler.add_job(
        send_weekly_auto_plan,
        CronTrigger(hour=7, minute=30, day_of_week="mon", timezone="Europe/Berlin"),
        id="weekly_auto_plan",
        max_instances=1,
        coalesce=True,
    )

    # Daily intelligence: morning context collection at 07:45 (after morning brief)
    _scheduler.add_job(
        run_morning_context_collection,
        CronTrigger(hour=7, minute=45, timezone="Europe/Berlin"),
        id="morning_context_collection",
        max_instances=1,
        coalesce=True,
    )

    # Daily intelligence: interactive evening check-in at 21:00
    _scheduler.add_job(
        run_evening_checkin,
        CronTrigger(hour=21, minute=0, timezone="Europe/Berlin"),
        id="evening_checkin",
        max_instances=1,
        coalesce=True,
    )

    # Daily intelligence: streak risk alerts at 10:00 (inline-button flow)
    _scheduler.add_job(
        run_streak_risk_check,
        CronTrigger(hour=10, minute=0, timezone="Europe/Berlin"),
        id="streak_risk_check_intelligence",
        max_instances=1,
        coalesce=True,
    )

    # Day planner: generate time-blocked schedule at 06:00 (before morning brief)
    _scheduler.add_job(
        run_day_planner,
        CronTrigger(hour=6, minute=0, timezone="Europe/Berlin"),
        id="day_planner",
        max_instances=1,
        coalesce=True,
    )

    # Journal prompt: daily 07:30
    _scheduler.add_job(
        send_journal_prompts,
        CronTrigger(hour=7, minute=30, timezone="Europe/Berlin"),
        id="journal_prompt",
        max_instances=1,
        coalesce=True,
    )

    # Gratitude prompt: daily 21:15
    _scheduler.add_job(
        send_gratitude_prompts,
        CronTrigger(hour=21, minute=15, timezone="Europe/Berlin"),
        id="gratitude_prompt",
        max_instances=1,
        coalesce=True,
    )

    # Post-event follow-up: every 15 minutes
    _scheduler.add_job(
        process_post_event_followups,
        "interval",
        minutes=15,
        id="post_event_followup",
        max_instances=1,
        coalesce=True,
    )

    # Pattern analysis: Sundays at 08:30 (after weekly reflection trigger)
    _scheduler.add_job(
        run_weekly_pattern_analysis,
        CronTrigger(hour=8, minute=30, day_of_week="sun", timezone="Europe/Berlin"),
        id="pattern_analysis",
        max_instances=1,
        coalesce=True,
    )

    logger.info(
        "Scheduler initialized with 17 active jobs: daily_suggestions, morning_brief, "
        "evening_review, reminders, weekly_reflection, ical_sync, gap_nudge, "
        "streak_risk_check, weekly_auto_plan, morning_context_collection, "
        "evening_checkin, streak_risk_check_intelligence, day_planner, "
        "journal_prompt, gratitude_prompt, post_event_followup, pattern_analysis"
    )
    return _scheduler
