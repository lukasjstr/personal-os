"""Phase 4: APScheduler setup with all proactive jobs active."""
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from bot.core.daily_intelligence import (
    run_evening_checkin,
    run_morning_context_collection,
    run_streak_risk_check,
)
from bot.core.plan_coherence import run_weekly_kickoff
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
from bot.jobs.learning_reminders import send_learning_reminders

logger = logging.getLogger(__name__)
_log = logger  # alias used by inline job wrappers

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

    # Learning reminders: daily at 09:30
    _scheduler.add_job(
        send_learning_reminders,
        CronTrigger(hour=9, minute=30, timezone="Europe/Berlin"),
        id="learning_reminders",
        max_instances=1,
        coalesce=True,
    )

    # Weekly calendar kickoff: Mondays at 08:15 (calendar overview + conflict detection)
    _scheduler.add_job(
        run_weekly_kickoff,
        CronTrigger(hour=8, minute=15, day_of_week="mon", timezone="Europe/Berlin"),
        id="weekly_kickoff",
        max_instances=1,
        coalesce=True,
    )

    # Life profile update: Mondays at 05:00 (weekly compressed memory update)
    async def _run_life_profile_update() -> None:
        import logging as _logging
        _log = _logging.getLogger(__name__)
        try:
            from bot.database.connection import get_session
            from bot.core.life_profile import update_life_profile
            from sqlalchemy import select as _select
            from bot.database.models import User as _User
            async with get_session() as _session:
                users_result = await _session.execute(
                    _select(_User).where(_User.is_active == True)  # noqa: E712
                )
                users = users_result.scalars().all()
                for _user in users:
                    try:
                        await update_life_profile(_session, _user.id)
                        await _session.commit()
                        _log.info("Life profile updated for user %s", _user.id)
                    except Exception:
                        _log.exception("Life profile update failed for user %s", _user.id)
        except Exception:
            _log.exception("Life profile update job failed")

    _scheduler.add_job(
        _run_life_profile_update,
        CronTrigger(hour=5, minute=0, day_of_week="mon", timezone="Europe/Berlin"),
        id="life_profile_update",
        max_instances=1,
        coalesce=True,
    )

    # Quarterly review: Jan 1, Apr 1, Jul 1, Oct 1 at 09:00
    async def _run_quarterly_review() -> None:
        import logging as _logging
        _log = _logging.getLogger(__name__)
        try:
            from bot.database.connection import get_session
            from bot.core.quarterly_review import generate_quarterly_review
            from sqlalchemy import select as _select
            from bot.database.models import User as _User
            async with get_session() as _session:
                users_result = await _session.execute(
                    _select(_User).where(_User.is_active == True)  # noqa: E712
                )
                users = users_result.scalars().all()
                for _user in users:
                    try:
                        await generate_quarterly_review(_session, _user.id)
                        _log.info("Quarterly review generated for user %s", _user.id)
                    except Exception:
                        _log.exception("Failed quarterly review for user %s", _user.id)
        except Exception:
            _log.exception("Quarterly review job failed")

    _scheduler.add_job(
        _run_quarterly_review,
        CronTrigger(month="1,4,7,10", day=1, hour=9, minute=0, timezone="Europe/Berlin"),
        id="quarterly_review",
        max_instances=1,
        coalesce=True,
    )

    # ── Action Engine: Autonomous Decision Layer ──────────────────────────────

    async def _run_action_engine_morning():
        from bot.core.action_engine import run_morning_actions
        from bot.core.kill_switches import is_enabled
        if not is_enabled("autopilot_nudges"):
            return
        from bot.database.connection import get_session
        from bot.database.models import User
        from sqlalchemy import select
        async with get_session() as session:
            users = (await session.execute(
                select(User).where(User.is_active == True)  # noqa: E712
            )).scalars().all()
            for user in users:
                try:
                    await run_morning_actions(session, user.id)
                    await session.commit()
                except Exception:
                    _log.exception("Morning action engine failed for user %d", user.id)

    _scheduler.add_job(
        _run_action_engine_morning,
        CronTrigger(hour=6, minute=15, timezone="Europe/Berlin"),
        id="action_engine_morning",
        max_instances=1,
        coalesce=True,
    )

    async def _run_action_engine_evening():
        from bot.core.action_engine import run_evening_actions
        from bot.core.kill_switches import is_enabled
        if not is_enabled("autopilot_nudges"):
            return
        from bot.database.connection import get_session
        from bot.database.models import User
        from sqlalchemy import select
        async with get_session() as session:
            users = (await session.execute(
                select(User).where(User.is_active == True)  # noqa: E712
            )).scalars().all()
            for user in users:
                try:
                    await run_evening_actions(session, user.id)
                    await session.commit()
                except Exception:
                    _log.exception("Evening action engine failed for user %d", user.id)

    _scheduler.add_job(
        _run_action_engine_evening,
        CronTrigger(hour=21, minute=30, timezone="Europe/Berlin"),
        id="action_engine_evening",
        max_instances=1,
        coalesce=True,
    )

    async def _run_action_engine_weekly():
        from bot.core.action_engine import run_weekly_actions
        from bot.core.kill_switches import is_enabled
        if not is_enabled("autopilot_nudges"):
            return
        from bot.database.connection import get_session
        from bot.database.models import User
        from sqlalchemy import select
        async with get_session() as session:
            users = (await session.execute(
                select(User).where(User.is_active == True)  # noqa: E712
            )).scalars().all()
            for user in users:
                try:
                    await run_weekly_actions(session, user.id)
                    await session.commit()
                except Exception:
                    _log.exception("Weekly action engine failed for user %d", user.id)

    _scheduler.add_job(
        _run_action_engine_weekly,
        CronTrigger(hour=9, minute=0, day_of_week="sun", timezone="Europe/Berlin"),
        id="action_engine_weekly",
        max_instances=1,
        coalesce=True,
    )

    # ── Realtime Interventions: every 60 minutes during active hours ────────
    async def _run_realtime_interventions():
        try:
            from bot.database.connection import get_session
            from bot.database.models import User
            from bot.core.realtime_interventions import run_all_interventions, format_intervention_message
            from bot.telegram.sender import send_message
            from sqlalchemy import select
            from zoneinfo import ZoneInfo
            from datetime import datetime as _dt
            now_berlin = _dt.now(tz=ZoneInfo("Europe/Berlin"))
            if not (8 <= now_berlin.hour <= 22):
                return
            async with get_session() as session:
                users = (await session.execute(
                    select(User).where(User.is_active == True)  # noqa: E712
                )).scalars().all()
                for user in users:
                    try:
                        interventions = await run_all_interventions(session, user.id)
                        for intervention in interventions[:2]:
                            msg = format_intervention_message(intervention)
                            await send_message(user.telegram_id, msg)
                    except Exception:
                        _log.exception("Intervention failed for user %d", user.id)
        except Exception:
            _log.exception("Realtime interventions job failed")

    _scheduler.add_job(
        _run_realtime_interventions,
        "interval",
        minutes=60,
        id="realtime_interventions",
        max_instances=1,
        coalesce=True,
    )

    # ── Prediction Engine: daily at 05:30 ─────────────────────────────────
    async def _run_predictions():
        try:
            from bot.database.connection import get_session
            from bot.database.models import User
            from bot.core.prediction_engine import run_all_predictions
            from sqlalchemy import select
            async with get_session() as session:
                users = (await session.execute(
                    select(User).where(User.is_active == True)  # noqa: E712
                )).scalars().all()
                for user in users:
                    try:
                        await run_all_predictions(session, user.id)
                        await session.commit()
                        _log.info("Predictions updated for user %d", user.id)
                    except Exception:
                        _log.exception("Prediction engine failed for user %d", user.id)
        except Exception:
            _log.exception("Prediction engine job failed")

    _scheduler.add_job(
        _run_predictions,
        CronTrigger(hour=5, minute=30, timezone="Europe/Berlin"),
        id="prediction_engine",
        max_instances=1,
        coalesce=True,
    )

    # ── Adaptive Goals: Sundays at 09:30 ──────────────────────────────────
    async def _run_adaptive_goals():
        try:
            from bot.database.connection import get_session
            from bot.database.models import User
            from bot.core.adaptive_goals import run_adaptive_analysis
            from bot.telegram.sender import send_message
            from sqlalchemy import select
            async with get_session() as session:
                users = (await session.execute(
                    select(User).where(User.is_active == True)  # noqa: E712
                )).scalars().all()
                for user in users:
                    try:
                        result = await run_adaptive_analysis(session, user.id)
                        await session.commit()
                        total = len(result.get("reductions", [])) + len(result.get("increases", [])) + len(result.get("progressive_overloads", []))
                        if total > 0:
                            await send_message(
                                user.telegram_id,
                                f"🎯 *Ziel-Check abgeschlossen*\n\n"
                                f"{total} Anpassungsvorschläge für dich. "
                                f"Schreib 'Ziel-Check' um sie zu sehen."
                            )
                    except Exception:
                        _log.exception("Adaptive goals failed for user %d", user.id)
        except Exception:
            _log.exception("Adaptive goals job failed")

    _scheduler.add_job(
        _run_adaptive_goals,
        CronTrigger(hour=9, minute=30, day_of_week="sun", timezone="Europe/Berlin"),
        id="adaptive_goals",
        max_instances=1,
        coalesce=True,
    )

    # ── Nutrition Daily Summary: daily at 21:45 ───────────────────────────
    async def _run_nutrition_summary():
        try:
            from bot.database.connection import get_session
            from bot.database.models import User
            from bot.core.nutrition_intelligence import get_daily_totals, check_nutrient_alerts
            from bot.core.causal_knowledge import get_daily_health_tips
            from bot.telegram.sender import send_message
            from sqlalchemy import select
            from datetime import date as _date
            async with get_session() as session:
                users = (await session.execute(
                    select(User).where(User.is_active == True)  # noqa: E712
                )).scalars().all()
                for user in users:
                    try:
                        today = _date.today()
                        totals = await get_daily_totals(session, user.id, today)
                        if not totals or totals.get("calories", 0) == 0:
                            continue
                        alerts = await check_nutrient_alerts(session, user.id, today)
                        lines = ["🍽️ *Ernährungs-Tagesbilanz*\n"]
                        lines.append(f"Kalorien: {totals.get('calories', 0):.0f}")
                        lines.append(f"Protein: {totals.get('protein_g', 0):.0f}g | Fett: {totals.get('fat_g', 0):.0f}g | KH: {totals.get('carbs_g', 0):.0f}g")
                        sod = totals.get("sodium_mg", 0)
                        if sod > 0:
                            lines.append(f"Natrium: {sod:.0f}mg | Koffein: {totals.get('caffeine_mg', 0):.0f}mg")
                        if alerts:
                            lines.append("\n⚠️ *Hinweise:*")
                            for a in alerts[:3]:
                                lines.append(f"• {a.get('message', '')}")
                        await send_message(user.telegram_id, "\n".join(lines))
                    except Exception:
                        _log.exception("Nutrition summary failed for user %d", user.id)
        except Exception:
            _log.exception("Nutrition summary job failed")

    _scheduler.add_job(
        _run_nutrition_summary,
        CronTrigger(hour=21, minute=45, timezone="Europe/Berlin"),
        id="nutrition_daily_summary",
        max_instances=1,
        coalesce=True,
    )

    # ── Huawei Health Kit Sync (daily at 06:00) ──────────────────────────────
    async def _run_huawei_sync():
        """Sync yesterday's health data from Huawei Health Kit for all connected users."""
        try:
            from bot.core.huawei_health_kit import sync_huawei_health
            from bot.database.connection import AsyncSessionLocal
            from bot.database.models import User
            from sqlalchemy import select

            async with AsyncSessionLocal() as session:
                users = (await session.execute(
                    select(User).where(User.is_active.is_(True))
                )).scalars().all()

                for user in users:
                    settings = user.settings or {}
                    if not settings.get("huawei_refresh_token"):
                        continue  # Not connected
                    try:
                        result = await sync_huawei_health(session, user)
                        if result.get("stored"):
                            _log.info("Huawei sync for user %d: %s", user.id, result["stored"])
                    except Exception:
                        _log.exception("Huawei sync failed for user %d", user.id)
                await session.commit()
        except Exception:
            _log.exception("Huawei Health sync job failed")

    _scheduler.add_job(
        _run_huawei_sync,
        CronTrigger(hour=6, minute=0, timezone="Europe/Berlin"),
        id="huawei_health_sync",
        max_instances=1,
        coalesce=True,
    )

    logger.info(
        "Scheduler initialized with 30 active jobs: daily_suggestions, morning_brief, "
        "evening_review, reminders, weekly_reflection, ical_sync, gap_nudge, "
        "streak_risk_check, weekly_auto_plan, morning_context_collection, "
        "evening_checkin, streak_risk_check_intelligence, day_planner, "
        "journal_prompt, gratitude_prompt, post_event_followup, pattern_analysis, "
        "quarterly_review, learning_reminders, life_profile_update, "
        "action_engine_morning, action_engine_evening, action_engine_weekly, "
        "weekly_kickoff, realtime_interventions, prediction_engine, "
        "adaptive_goals, nutrition_daily_summary, huawei_health_sync"
    )
    return _scheduler
