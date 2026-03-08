"""P2.3 — Daily suggestions pipeline.

Generates 3-5 proactive nudges per day based on:
  - Missed routines yesterday
  - Overdue tasks (>3 days)
  - Stalled objectives (no task completed in 7 days)
  - No brain dump in 3 days
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import BrainDump, Objective, Routine, RoutineCompletion, Task


async def generate_daily_suggestions(
    session: AsyncSession,
    user_id: int,
) -> list[dict[str, Any]]:
    """Generate up to 5 proactive daily suggestions for the user."""
    today = date.today()
    yesterday = today - timedelta(days=1)
    three_days_ago = today - timedelta(days=3)
    seven_days_ago = today - timedelta(days=7)
    suggestions: list[dict[str, Any]] = []

    # ── 1. Missed routines yesterday ─────────────────────────────────────────
    active_routines_res = await session.execute(
        select(Routine).where(
            and_(Routine.user_id == user_id, Routine.status == "active")
        )
    )
    active_routines = active_routines_res.scalars().all()

    yesterday_start = datetime.combine(yesterday, datetime.min.time())
    yesterday_end = datetime.combine(today, datetime.min.time())
    completed_yesterday_res = await session.execute(
        select(RoutineCompletion.routine_id).where(
            and_(
                RoutineCompletion.user_id == user_id,
                RoutineCompletion.completed_at >= yesterday_start,
                RoutineCompletion.completed_at < yesterday_end,
            )
        )
    )
    completed_yesterday_ids = {row[0] for row in completed_yesterday_res.all()}

    for r in active_routines:
        if r.id not in completed_yesterday_ids:
            suggestions.append({
                "type": "missed_routine",
                "message": f"Gestern {r.title} nicht gemacht — heute wieder starten?",
                "action_hint": "routine",
            })
        if len(suggestions) >= 2:
            break

    # ── 2. Overdue tasks (>3 days) ───────────────────────────────────────────
    overdue_res = await session.execute(
        select(Task).where(
            and_(
                Task.user_id == user_id,
                Task.due_date < three_days_ago,
                Task.status.notin_(["done", "cancelled"]),
            )
        ).order_by(Task.due_date.asc()).limit(2)
    )
    for t in overdue_res.scalars().all():
        n = (today - t.due_date).days
        suggestions.append({
            "type": "overdue_task",
            "message": f'"{t.title}" ist {n} {"Tag" if n == 1 else "Tage"} überfällig',
            "action_hint": "task",
        })

    # ── 3. Stalled objectives ────────────────────────────────────────────────
    if len(suggestions) < 4:
        active_obj_res = await session.execute(
            select(Objective).where(
                and_(Objective.user_id == user_id, Objective.status == "active")
            )
        )
        for obj in active_obj_res.scalars().all():
            recent_done_res = await session.execute(
                select(func.count()).select_from(Task).where(
                    and_(
                        Task.objective_id == obj.id,
                        Task.status == "done",
                        Task.completed_at >= datetime.combine(seven_days_ago, datetime.min.time()),
                    )
                )
            )
            count = recent_done_res.scalar() or 0
            if count == 0:
                suggestions.append({
                    "type": "stalled_objective",
                    "message": f'Kein Fortschritt bei "{obj.title}" diese Woche',
                    "action_hint": "objective",
                })
                break  # one stalled-objective nudge per run

    # ── 4. No brain dump in 3 days ───────────────────────────────────────────
    if len(suggestions) < 5:
        recent_dump_res = await session.execute(
            select(func.count()).select_from(BrainDump).where(
                and_(
                    BrainDump.user_id == user_id,
                    BrainDump.created_at >= datetime.combine(three_days_ago, datetime.min.time()),
                )
            )
        )
        if (recent_dump_res.scalar() or 0) == 0:
            suggestions.append({
                "type": "brain_dump_nudge",
                "message": "Zeit für einen Brain Dump — was beschäftigt dich?",
                "action_hint": "brain_dump",
            })

    return suggestions[:5]
