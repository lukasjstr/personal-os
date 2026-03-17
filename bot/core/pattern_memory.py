"""Sprint 4: Pattern Memory — analyzes user's productivity patterns over time.

Runs weekly (Sunday) to identify:
- Best productive days/times
- Habit completion patterns
- Task completion rates by category
- Energy-performance correlations (when DailyContext data exists)
- Routine adherence trends
"""
import logging
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import (
    DailyContext, EveningCheckin, Objective, Routine,
    RoutineCompletion, Task, User,
)

logger = logging.getLogger(__name__)


async def compute_productivity_patterns(
    session: AsyncSession,
    user: User,
    days: int = 28,
) -> dict[str, Any]:
    """Compute productivity patterns for the past N days.

    Returns a structured dict with:
    - task_stats: completion rates by day of week, by category
    - routine_stats: completion rates by routine, trend
    - energy_stats: if DailyContext data exists, correlate energy with task completion
    - best_day: day of week with highest task completion
    - consistency_score: 0-100 how consistent the user has been
    - patterns: list of human-readable pattern observations
    """
    today = date.today()
    cutoff = datetime.combine(today - timedelta(days=days), datetime.min.time())

    # ── Task completion by day of week ────────────────────────────────────────
    done_tasks_res = await session.execute(
        select(Task.completed_at, Task.category)
        .where(and_(
            Task.user_id == user.id,
            Task.status == "done",
            Task.completed_at >= cutoff,
        ))
    )
    done_tasks = done_tasks_res.all()

    by_day: dict[int, int] = {i: 0 for i in range(7)}  # 0=Monday
    by_category: dict[str, int] = {}
    for completed_at, category in done_tasks:
        if completed_at:
            by_day[completed_at.weekday()] += 1
        if category:
            by_category[category] = by_category.get(category, 0) + 1

    # Total open tasks created in period
    open_res = await session.execute(
        select(func.count()).select_from(Task).where(and_(
            Task.user_id == user.id,
            Task.created_at >= cutoff,
        ))
    )
    total_tasks_created = open_res.scalar() or 1
    total_done = len(done_tasks)

    overall_completion_rate = min(100, int((total_done / total_tasks_created) * 100))

    day_names = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
    best_day_idx = max(by_day, key=by_day.get)
    best_day = day_names[best_day_idx]
    worst_day_idx = min(by_day, key=by_day.get)
    worst_day = day_names[worst_day_idx]

    # ── Routine adherence ─────────────────────────────────────────────────────
    routine_res = await session.execute(
        select(Routine).where(and_(Routine.user_id == user.id, Routine.is_active == True))
    )
    routines = routine_res.scalars().all()

    routine_stats = []
    for routine in routines:
        completions_res = await session.execute(
            select(func.count()).select_from(RoutineCompletion).where(and_(
                RoutineCompletion.routine_id == routine.id,
                RoutineCompletion.completed_at >= cutoff,
            ))
        )
        completions = completions_res.scalar() or 0
        # Expected: roughly days/7 per week frequency
        expected = days  # daily routine expected = days completions
        adherence = min(100, int((completions / max(1, expected // 7 * 3)) * 100))
        routine_stats.append({
            "name": routine.name,
            "completions": completions,
            "adherence_pct": adherence,
        })

    routine_stats.sort(key=lambda x: x["adherence_pct"], reverse=True)

    # ── Evening check-in stats ────────────────────────────────────────────────
    checkin_res = await session.execute(
        select(EveningCheckin).where(and_(
            EveningCheckin.user_id == user.id,
            EveningCheckin.created_at >= cutoff,
        ))
    )
    checkins = checkin_res.scalars().all()

    avg_completion_rate = 0
    if checkins:
        rates = [
            c.tasks_completed / max(1, c.tasks_planned) * 100
            for c in checkins if c.tasks_planned > 0
        ]
        avg_completion_rate = int(sum(rates) / len(rates)) if rates else 0

    # ── Energy correlation ────────────────────────────────────────────────────
    ctx_res = await session.execute(
        select(DailyContext).where(and_(
            DailyContext.user_id == user.id,
            DailyContext.created_at >= cutoff,
        ))
    )
    contexts = ctx_res.scalars().all()

    energy_insight = None
    if len(contexts) >= 7:
        high_energy_days = [c for c in contexts if c.energy and c.energy >= 7]
        low_energy_days = [c for c in contexts if c.energy and c.energy <= 4]
        avg_energy = int(sum(c.energy for c in contexts if c.energy) / len(contexts))
        energy_insight = {
            "avg_energy": avg_energy,
            "high_energy_days": len(high_energy_days),
            "low_energy_days": len(low_energy_days),
            "trend": "steigend" if avg_energy >= 7 else "fallend" if avg_energy <= 4 else "stabil",
        }

    # ── Consistency score ─────────────────────────────────────────────────────
    # Score = weighted average of: task completion rate + routine adherence + check-in rate
    checkin_rate = min(100, int((len(checkins) / days) * 100 * 7))  # expected ~4/week
    routine_avg = int(sum(r["adherence_pct"] for r in routine_stats) / len(routine_stats)) if routine_stats else 50
    consistency_score = int(
        overall_completion_rate * 0.4
        + routine_avg * 0.35
        + checkin_rate * 0.25
    )

    # ── Pattern observations ──────────────────────────────────────────────────
    patterns = []

    if by_day[best_day_idx] > 0:
        patterns.append(f"📈 Du bist am {best_day} am produktivsten ({by_day[best_day_idx]} Tasks erledigt)")

    if by_day[worst_day_idx] == 0:
        patterns.append(f"⚠️ Am {worst_day} erledigst du kaum Tasks — vielleicht ein Ruhetag?")

    if by_category:
        top_cat = max(by_category, key=by_category.get)
        patterns.append(f"🎯 Die meisten erledigten Tasks kommen aus: {top_cat}")

    if routine_stats:
        best_routine = routine_stats[0]
        if best_routine["adherence_pct"] >= 70:
            patterns.append(f"✅ Routine '{best_routine['name']}' hältst du sehr gut ein ({best_routine['adherence_pct']}%)")
        worst_routine = routine_stats[-1]
        if worst_routine["adherence_pct"] < 40:
            patterns.append(f"⚠️ Routine '{worst_routine['name']}' wird oft übersprungen ({worst_routine['adherence_pct']}%)")

    if overall_completion_rate >= 70:
        patterns.append(f"🚀 Starke Woche! Du erledigst {overall_completion_rate}% deiner Tasks")
    elif overall_completion_rate < 30:
        patterns.append(f"💡 Tipp: Weniger Tasks planen, dafür die richtigen — aktuell {overall_completion_rate}% Completion")

    return {
        "period_days": days,
        "overall_completion_rate": overall_completion_rate,
        "total_tasks_done": total_done,
        "best_productive_day": best_day,
        "tasks_by_day": {day_names[i]: v for i, v in by_day.items()},
        "tasks_by_category": by_category,
        "routine_stats": routine_stats[:5],
        "consistency_score": consistency_score,
        "energy_insight": energy_insight,
        "checkin_count": len(checkins),
        "avg_daily_completion_rate": avg_completion_rate,
        "patterns": patterns,
    }
