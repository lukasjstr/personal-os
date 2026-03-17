"""Predictive Life Engine — statistical pattern analysis over historical data.

Runs weekly (Sunday) and on-demand. Generates UserInsight records with
concrete predictions and recommendations.

Analyses performed:
1. KR weekly completion rate → "Du erfüllst Cardio nur 58% der Wochen"
2. Day-of-week patterns → "Di/Mi/Do: deine produktivsten Tage"
3. Mood correlation → "Mood ist 1.8 Punkte höher an Training-Tagen"
4. Dead goal detection → "OBJ#32 hat seit 18 Tagen keine Aktivität"
5. Routine skip analysis → "Morgen-Journal: häufigster Skip-Tag = Montag"
6. Consistency score → 0-100 across all dimensions
7. Streak risk → KRs where current pace predicts failure
"""
from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date, datetime, timedelta
from statistics import mean, stdev
from typing import Optional

from sqlalchemy import and_, extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import (
    EveningCheckin, KeyResult, Log, Objective,
    Routine, RoutineCompletion, Task, UserInsight,
)

logger = logging.getLogger(__name__)

# How many weeks back to analyze
ANALYSIS_WEEKS = 8
MIN_DATA_POINTS = 3  # Skip analysis if fewer than this many data points


# ─── Main entry point ────────────────────────────────────────────────────────

async def run_pattern_analysis(session: AsyncSession, user_id: int) -> dict:
    """Run all analyses, store insights, return summary dict."""
    today = date.today()
    insights: list[dict] = []

    try:
        insights += await _analyze_kr_completion_rates(session, user_id, today)
    except Exception:
        logger.exception("KR completion rate analysis failed")

    try:
        insights += await _analyze_day_of_week_patterns(session, user_id, today)
    except Exception:
        logger.exception("Day-of-week analysis failed")

    try:
        insights += await _analyze_mood_correlations(session, user_id, today)
    except Exception:
        logger.exception("Mood correlation analysis failed")

    try:
        insights += await _analyze_dead_goals(session, user_id, today)
    except Exception:
        logger.exception("Dead goal analysis failed")

    try:
        insights += await _analyze_routine_skip_patterns(session, user_id, today)
    except Exception:
        logger.exception("Routine skip analysis failed")

    try:
        consistency = await _compute_consistency_score(session, user_id, today)
    except Exception:
        logger.exception("Consistency score failed")
        consistency = None

    # Deactivate old auto-detected insights and write fresh ones
    old = await session.execute(
        select(UserInsight).where(and_(
            UserInsight.user_id == user_id,
            UserInsight.source == "auto_detected",
        ))
    )
    for old_insight in old.scalars().all():
        old_insight.active = False

    stored = []
    for ins in insights:
        ui = UserInsight(
            user_id=user_id,
            insight_type=ins["type"],
            title=ins["title"],
            description=ins["description"],
            source="auto_detected",
            active=True,
            data_basis=ins.get("data"),
        )
        session.add(ui)
        stored.append(ins)

    await session.flush()
    logger.info("Pattern analysis for user %s: %d insights generated", user_id, len(stored))

    return {
        "insights": stored,
        "consistency_score": consistency,
        "generated_at": datetime.utcnow().isoformat(),
    }


async def get_pattern_summary(session: AsyncSession, user_id: int) -> str:
    """Return a short context string for the AI prompt (<=12 lines)."""
    result = await session.execute(
        select(UserInsight).where(and_(
            UserInsight.user_id == user_id,
            UserInsight.source == "auto_detected",
            UserInsight.active == True,  # noqa: E712
        )).order_by(UserInsight.created_at.desc()).limit(6)
    )
    insights = result.scalars().all()
    if not insights:
        return ""

    lines = ["=== MUSTER & VORHERSAGEN ==="]
    for ins in insights:
        icon = _insight_icon(ins.insight_type)
        lines.append(f"  {icon} {ins.title}: {ins.description}")
    return "\n".join(lines)


# ─── Analysis 1: KR Completion Rates ─────────────────────────────────────────

async def _analyze_kr_completion_rates(
    session: AsyncSession, user_id: int, today: date
) -> list[dict]:
    """Per active KR: % of weeks where progress was logged in last ANALYSIS_WEEKS weeks."""
    kr_result = await session.execute(
        select(KeyResult).where(and_(
            KeyResult.user_id == user_id,
            KeyResult.status == "active",
            KeyResult.frequency == "daily",  # only daily KRs make sense for weekly rate
        ))
    )
    krs = kr_result.scalars().all()

    insights = []
    since = today - timedelta(weeks=ANALYSIS_WEEKS)

    for kr in krs:
        # Count distinct weeks where progress was logged
        logs_result = await session.execute(
            select(Log).where(and_(
                Log.user_id == user_id,
                Log.log_type == "progress",
                Log.key_result_id == kr.id,
                Log.logged_at >= datetime.combine(since, datetime.min.time()),
            ))
        )
        logs = logs_result.scalars().all()

        if len(logs) < MIN_DATA_POINTS:
            continue

        weeks_with_progress = len({l.logged_at.isocalendar()[1] for l in logs})
        completion_rate = weeks_with_progress / ANALYSIS_WEEKS

        if completion_rate < 0.6:
            pct = int(completion_rate * 100)
            insights.append({
                "type": "kr_risk",
                "title": f"KR '{kr.title[:40]}' unter Plan",
                "description": f"Nur {pct}% der Wochen erfüllt (letzte {ANALYSIS_WEEKS} Wochen). Aktuell: {kr.current_value:.0f}/{kr.target_value:.0f}.",
                "data": {"kr_id": kr.id, "completion_rate": completion_rate, "weeks": ANALYSIS_WEEKS},
            })
        elif completion_rate >= 0.9:
            pct = int(completion_rate * 100)
            insights.append({
                "type": "strength",
                "title": f"KR '{kr.title[:40]}' — starke Konsistenz",
                "description": f"{pct}% Erfüllungsrate — du bist auf Kurs. Weiter so!",
                "data": {"kr_id": kr.id, "completion_rate": completion_rate},
            })

    return insights


# ─── Analysis 2: Day-of-Week Productivity ─────────────────────────────────────

async def _analyze_day_of_week_patterns(
    session: AsyncSession, user_id: int, today: date
) -> list[dict]:
    """Find best and worst days of week for routine completions."""
    since = datetime.combine(today - timedelta(weeks=ANALYSIS_WEEKS), datetime.min.time())

    comps_result = await session.execute(
        select(RoutineCompletion).where(and_(
            RoutineCompletion.user_id == user_id,
            RoutineCompletion.completed_at >= since,
        ))
    )
    completions = comps_result.scalars().all()

    if len(completions) < MIN_DATA_POINTS * 2:
        return []

    day_counts: dict[int, int] = defaultdict(int)  # weekday (0=Mon) → count
    day_totals: dict[int, int] = defaultdict(int)   # weekday → days in period with that weekday

    for comp in completions:
        dow = comp.completed_at.weekday()
        day_counts[dow] += 1

    # Count how many of each weekday occurred in the analysis period
    for i in range(ANALYSIS_WEEKS * 7):
        d = today - timedelta(days=i)
        day_totals[d.weekday()] += 1

    # Compute average completions per weekday occurrence
    DOW_NAMES = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
    rates = {}
    for dow in range(7):
        if day_totals[dow] > 0:
            rates[dow] = day_counts[dow] / day_totals[dow]

    if len(rates) < 5:
        return []

    best_day = max(rates, key=lambda d: rates[d])
    worst_day = min(rates, key=lambda d: rates[d])
    avg_rate = mean(rates.values())

    insights = []
    if rates[best_day] > avg_rate * 1.3:
        insights.append({
            "type": "productivity_pattern",
            "title": f"Stärkster Tag: {DOW_NAMES[best_day]}",
            "description": f"Durchschnittlich {rates[best_day]:.1f} Routinen abgeschlossen — {int((rates[best_day]/avg_rate - 1)*100)}% über Durchschnitt.",
            "data": {"best_dow": best_day, "rates": {str(k): round(v, 2) for k, v in rates.items()}},
        })
    if rates[worst_day] < avg_rate * 0.7:
        insights.append({
            "type": "blocker",
            "title": f"Schwächster Tag: {DOW_NAMES[worst_day]}",
            "description": f"Nur {rates[worst_day]:.1f} Routinen im Schnitt — {int((1 - rates[worst_day]/avg_rate)*100)}% unter Durchschnitt. Weniger einplanen oder Energie-Routine stärken.",
            "data": {"worst_dow": worst_day, "rates": {str(k): round(v, 2) for k, v in rates.items()}},
        })
    return insights


# ─── Analysis 3: Mood Correlation ─────────────────────────────────────────────

async def _analyze_mood_correlations(
    session: AsyncSession, user_id: int, today: date
) -> list[dict]:
    """Correlate mood scores with training / routine completion."""
    since = datetime.combine(today - timedelta(weeks=ANALYSIS_WEEKS), datetime.min.time())

    mood_logs = (await session.execute(
        select(Log).where(and_(
            Log.user_id == user_id,
            Log.log_type == "mood",
            Log.logged_at >= since,
        ))
    )).scalars().all()

    if len(mood_logs) < MIN_DATA_POINTS:
        return []

    # Group mood by date
    mood_by_date: dict[date, float] = {}
    for m in mood_logs:
        d = m.logged_at.date()
        score = m.data.get("score", 0)
        if score:
            mood_by_date[d] = float(score)

    if len(mood_by_date) < MIN_DATA_POINTS:
        return []

    # Check workout days
    workout_logs = (await session.execute(
        select(Log).where(and_(
            Log.user_id == user_id,
            Log.log_type == "workout",
            Log.logged_at >= since,
        ))
    )).scalars().all()

    workout_dates = {w.logged_at.date() for w in workout_logs}

    insights = []
    if workout_dates:
        workout_moods = [mood_by_date[d] for d in workout_dates if d in mood_by_date]
        rest_moods = [v for d, v in mood_by_date.items() if d not in workout_dates]

        if len(workout_moods) >= MIN_DATA_POINTS and len(rest_moods) >= MIN_DATA_POINTS:
            wm_avg = mean(workout_moods)
            rm_avg = mean(rest_moods)
            diff = wm_avg - rm_avg

            if abs(diff) >= 0.5:
                direction = "höher" if diff > 0 else "niedriger"
                insights.append({
                    "type": "habit",
                    "title": f"Training → Mood {'+' if diff > 0 else ''}{diff:.1f} Punkte",
                    "description": f"An Training-Tagen ist deine Stimmung durchschnittlich {abs(diff):.1f} Punkte {direction} ({wm_avg:.1f} vs {rm_avg:.1f}). {'Trainiere heute!' if diff > 0 else 'Checke ob Training dich stresst.'}",
                    "data": {"workout_mood_avg": round(wm_avg, 2), "rest_mood_avg": round(rm_avg, 2), "diff": round(diff, 2)},
                })

    return insights


# ─── Analysis 4: Dead Goal Detection ──────────────────────────────────────────

async def _analyze_dead_goals(
    session: AsyncSession, user_id: int, today: date
) -> list[dict]:
    """Find active objectives with no task activity in the last 14 days."""
    fourteen_ago = datetime.combine(today - timedelta(days=14), datetime.min.time())

    obj_result = await session.execute(
        select(Objective).where(and_(
            Objective.user_id == user_id,
            Objective.status == "active",
        ))
    )
    objectives = obj_result.scalars().all()

    insights = []
    for obj in objectives:
        # Check for any task activity (created or completed) in last 14 days
        recent_tasks = (await session.execute(
            select(func.count()).select_from(Task).where(and_(
                Task.objective_id == obj.id,
                Task.updated_at >= fourteen_ago,
            ))
        )).scalar() or 0

        # Check for any KR progress in last 14 days
        recent_progress = (await session.execute(
            select(func.count()).select_from(Log).where(and_(
                Log.user_id == user_id,
                Log.log_type == "progress",
                Log.logged_at >= fourteen_ago,
                Log.key_result_id.in_(
                    select(KeyResult.id).where(KeyResult.objective_id == obj.id)
                ),
            ))
        )).scalar() or 0

        if recent_tasks == 0 and recent_progress == 0:
            # Find last activity date
            last_task = (await session.execute(
                select(Task.updated_at).where(Task.objective_id == obj.id)
                .order_by(Task.updated_at.desc()).limit(1)
            )).scalar_one_or_none()

            days_inactive = 14
            if last_task:
                days_inactive = (today - last_task.date()).days if hasattr(last_task, 'date') else 14

            insights.append({
                "type": "blocker",
                "title": f"Ziel ohne Aktivität: '{obj.title[:40]}'",
                "description": f"Seit {days_inactive}+ Tagen keine Fortschritte bei OBJ#{obj.id}. Noch aktuell? Nächsten Task definieren oder Ziel pausieren.",
                "data": {"objective_id": obj.id, "days_inactive": days_inactive},
            })

    return insights


# ─── Analysis 5: Routine Skip Patterns ────────────────────────────────────────

async def _analyze_routine_skip_patterns(
    session: AsyncSession, user_id: int, today: date
) -> list[dict]:
    """Find routines that are skipped most often and identify skip day patterns."""
    since = datetime.combine(today - timedelta(weeks=ANALYSIS_WEEKS), datetime.min.time())

    routines_result = await session.execute(
        select(Routine).where(and_(
            Routine.user_id == user_id,
            Routine.status == "active",
            Routine.frequency_human == "täglich",
        ))
    )
    routines = routines_result.scalars().all()

    total_days = ANALYSIS_WEEKS * 7
    insights = []

    for routine in routines:
        comps_result = await session.execute(
            select(RoutineCompletion).where(and_(
                RoutineCompletion.routine_id == routine.id,
                RoutineCompletion.completed_at >= since,
            ))
        )
        completions = comps_result.scalars().all()
        completion_rate = len(completions) / total_days if total_days > 0 else 0

        if completion_rate < 0.4:
            # Find most common skip day
            completed_dows = {c.completed_at.weekday() for c in completions}
            DOW_NAMES = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
            skipped_dows = [DOW_NAMES[d] for d in range(7) if d not in completed_dows]

            pct = int(completion_rate * 100)
            skip_info = f" — meist übersprungen: {', '.join(skipped_dows[:3])}" if skipped_dows else ""
            insights.append({
                "type": "habit",
                "title": f"Routine '{routine.title[:35]}' — nur {pct}% Konsistenz",
                "description": f"Nur {len(completions)}/{total_days} Tage abgeschlossen{skip_info}. Zu komplex? Verkürzen oder Zeit anpassen.",
                "data": {"routine_id": routine.id, "completion_rate": completion_rate, "skip_days": skipped_dows},
            })

    return insights


# ─── Analysis 6: Consistency Score ───────────────────────────────────────────

async def _compute_consistency_score(
    session: AsyncSession, user_id: int, today: date
) -> dict:
    """Compute overall consistency score 0-100 across all dimensions."""
    since = datetime.combine(today - timedelta(days=30), datetime.min.time())
    total_days = 30

    # Component 1: Routine completion rate (weight 40%)
    total_completions = (await session.execute(
        select(func.count()).select_from(RoutineCompletion).where(and_(
            RoutineCompletion.user_id == user_id,
            RoutineCompletion.completed_at >= since,
        ))
    )).scalar() or 0

    active_routines = (await session.execute(
        select(func.count()).select_from(Routine).where(and_(
            Routine.user_id == user_id,
            Routine.status == "active",
        ))
    )).scalar() or 1

    routine_rate = min(1.0, total_completions / (active_routines * total_days))

    # Component 2: Task completion rate (weight 30%)
    tasks_done = (await session.execute(
        select(func.count()).select_from(Task).where(and_(
            Task.user_id == user_id,
            Task.status == "done",
            Task.updated_at >= since,
        ))
    )).scalar() or 0

    tasks_total = (await session.execute(
        select(func.count()).select_from(Task).where(and_(
            Task.user_id == user_id,
            Task.status.in_(["done", "todo", "in_progress"]),
            Task.created_at >= since,
        ))
    )).scalar() or 1

    task_rate = min(1.0, tasks_done / tasks_total)

    # Component 3: Logging activity (weight 30%) — are they using the system?
    log_days = (await session.execute(
        select(func.count(func.distinct(func.date(Log.logged_at)))).where(and_(
            Log.user_id == user_id,
            Log.logged_at >= since,
        ))
    )).scalar() or 0

    logging_rate = min(1.0, log_days / total_days)

    score = int((routine_rate * 0.4 + task_rate * 0.3 + logging_rate * 0.3) * 100)

    emoji = "🟢" if score >= 75 else "🟡" if score >= 50 else "🔴"
    label = "Stark" if score >= 75 else "Mittel" if score >= 50 else "Niedrig"

    return {
        "score": score,
        "label": label,
        "emoji": emoji,
        "components": {
            "routine_rate": round(routine_rate * 100),
            "task_rate": round(task_rate * 100),
            "logging_rate": round(logging_rate * 100),
        },
    }


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _insight_icon(insight_type: str) -> str:
    return {
        "kr_risk": "⚠️",
        "strength": "💪",
        "productivity_pattern": "📈",
        "blocker": "🚧",
        "habit": "🔄",
        "preference": "💡",
    }.get(insight_type, "📊")
