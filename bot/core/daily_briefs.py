"""CORE-6: Daily brief creation and management.

Handles morning brief generation, evening review, and day scoring.
Integrates goal pipeline outputs (objectives, key results, scheduled reminders)
for warning detection and free-slot suggestions.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import (
    CalendarEvent,
    DailyBrief,
    KeyResult,
    Objective,
    Routine,
    ScheduledReminder,
    Task,
)

# ── Warning thresholds ────────────────────────────────────────────────────────
_DEADLINE_WARNING_DAYS: int = 7     # warn when objective deadline is within N days
_KR_BEHIND_THRESHOLD: float = 0.5  # warn when KR progress < 50% of target

# Reminder types that appear in the morning brief as actionable warnings
_HIGH_PRIORITY_REMINDER_TYPES: tuple[str, ...] = (
    "task_deadline",
    "streak_warning",
    "calendar_prep",
)


async def get_todays_brief(session: AsyncSession, user_id: int) -> Optional[DailyBrief]:
    """Return today's DailyBrief for *user_id*, or None if not yet created."""
    today = date.today()
    result = await session.execute(
        select(DailyBrief).where(
            DailyBrief.user_id == user_id,
            DailyBrief.brief_date == today,
        )
    )
    return result.scalar_one_or_none()


async def create_daily_brief(session: AsyncSession, user_id: int) -> DailyBrief:
    """Create (or refresh) today's daily brief for *user_id*.

    CORE-6: Integrates goal pipeline outputs — active objectives, key results,
    and pending reminders — to produce:
      - priorities:         top tasks due today + goal work-block suggestions
      - routines_snapshot:  active routines checklist
      - calendar_snapshot:  today's calendar events
      - warnings:           overdue tasks, approaching deadlines, behind KRs,
                            high-priority pending reminders
    """
    today = date.today()
    now = datetime.utcnow()

    priorities = await _build_priorities(session, user_id, today)
    routines_snapshot = await _build_routines_snapshot(session, user_id)
    calendar_snapshot = await _build_calendar_snapshot(session, user_id, today)
    warnings = await _detect_warnings(session, user_id, today, now)

    existing = await get_todays_brief(session, user_id)
    if existing is not None:
        existing.priorities = priorities
        existing.routines_snapshot = routines_snapshot
        existing.calendar_snapshot = calendar_snapshot
        existing.warnings = warnings
        await session.commit()
        await session.refresh(existing)
        return existing

    brief = DailyBrief(
        user_id=user_id,
        brief_date=today,
        priorities=priorities,
        routines_snapshot=routines_snapshot,
        calendar_snapshot=calendar_snapshot,
        warnings=warnings,
    )
    session.add(brief)
    await session.commit()
    await session.refresh(brief)
    return brief


async def update_brief_priorities(
    session: AsyncSession,
    brief_id: int,
    priorities: list[dict],
) -> DailyBrief:
    """Overwrite priorities with user-adjusted values and mark the brief as adjusted."""
    result = await session.execute(
        select(DailyBrief).where(DailyBrief.id == brief_id)
    )
    brief = result.scalar_one()
    brief.user_adjusted = True
    brief.adjusted_priorities = priorities
    await session.commit()
    await session.refresh(brief)
    return brief


async def save_day_score(
    session: AsyncSession,
    brief_id: int,
    score: int,
    notes: Optional[str] = None,
) -> DailyBrief:
    """Record end-of-day score (1–10) and optional notes during evening review."""
    result = await session.execute(
        select(DailyBrief).where(DailyBrief.id == brief_id)
    )
    brief = result.scalar_one()
    brief.day_score = score
    brief.day_notes = notes
    await session.commit()
    await session.refresh(brief)
    return brief


# ── Internal builders ─────────────────────────────────────────────────────────


async def _build_priorities(
    session: AsyncSession,
    user_id: int,
    today: date,
) -> list[dict]:
    """Top tasks due today or overdue, plus CORE-6 goal work-block suggestions."""
    tasks_result = await session.execute(
        select(Task)
        .where(
            Task.user_id == user_id,
            Task.status.in_(["todo", "in_progress"]),
            Task.due_date <= today,
        )
        .order_by(Task.priority, Task.due_date)
        .limit(5)
    )
    priority_items: list[dict] = [
        {
            "type": "task",
            "id": t.id,
            "title": t.title,
            "priority": t.priority,
            "due_date": t.due_date.isoformat() if t.due_date else None,
            "objective_id": t.objective_id,
        }
        for t in tasks_result.scalars().all()
    ]

    # CORE-6: append goal work-block suggestions from active objectives/KRs
    goal_slots = await _build_goal_slots_for_today(session, user_id, today)
    priority_items.extend(goal_slots)

    return priority_items[:8]  # cap total to keep brief scannable


async def _build_routines_snapshot(
    session: AsyncSession,
    user_id: int,
) -> list[dict]:
    """Active routines for the morning checklist."""
    result = await session.execute(
        select(Routine)
        .where(Routine.user_id == user_id, Routine.status == "active")
        .order_by(Routine.sort_order, Routine.id)
        .limit(20)
    )
    return [
        {
            "id": r.id,
            "title": r.title,
            "time_of_day": r.time_of_day,
            "frequency_human": r.frequency_human,
        }
        for r in result.scalars().all()
    ]


async def _build_calendar_snapshot(
    session: AsyncSession,
    user_id: int,
    today: date,
) -> list[dict]:
    """Calendar events starting today (UTC date window)."""
    day_start = datetime(today.year, today.month, today.day, 0, 0, 0)
    day_end = day_start + timedelta(days=1)
    result = await session.execute(
        select(CalendarEvent)
        .where(
            CalendarEvent.user_id == user_id,
            CalendarEvent.start_time >= day_start,
            CalendarEvent.start_time < day_end,
        )
        .order_by(CalendarEvent.start_time)
        .limit(20)
    )
    return [
        {
            "id": e.id,
            "title": e.title,
            "start_time": e.start_time.isoformat(),
            "end_time": e.end_time.isoformat() if e.end_time else None,
            "event_type": e.event_type,
            "all_day": e.all_day,
        }
        for e in result.scalars().all()
    ]


async def _detect_warnings(
    session: AsyncSession,
    user_id: int,
    today: date,
    now: datetime,
) -> list[dict]:
    """CORE-6 warning detector: overdue tasks, approaching deadlines, behind KRs,
    and high-priority pending reminders due today.
    """
    warnings: list[dict] = []

    # 1. Overdue tasks
    overdue_result = await session.execute(
        select(Task)
        .where(
            Task.user_id == user_id,
            Task.status.in_(["todo", "in_progress"]),
            Task.due_date < today,
        )
        .order_by(Task.due_date)
        .limit(5)
    )
    for t in overdue_result.scalars().all():
        warnings.append({
            "kind": "overdue_task",
            "task_id": t.id,
            "title": t.title,
            "due_date": t.due_date.isoformat(),
            "days_overdue": (today - t.due_date).days,
        })

    # 2. Objectives approaching their deadline
    deadline_cutoff = today + timedelta(days=_DEADLINE_WARNING_DAYS)
    obj_result = await session.execute(
        select(Objective)
        .where(
            Objective.user_id == user_id,
            Objective.status == "active",
            Objective.target_date != None,  # noqa: E711
            Objective.target_date >= today,
            Objective.target_date <= deadline_cutoff,
        )
        .order_by(Objective.target_date)
        .limit(5)
    )
    for obj in obj_result.scalars().all():
        warnings.append({
            "kind": "deadline_approaching",
            "objective_id": obj.id,
            "title": obj.title,
            "target_date": obj.target_date.isoformat(),
            "days_left": (obj.target_date - today).days,
        })

    # 3. Key results behind target (< 50% progress) with an approaching deadline
    kr_result = await session.execute(
        select(KeyResult)
        .where(
            KeyResult.user_id == user_id,
            KeyResult.status == "active",
            KeyResult.target_value != None,  # noqa: E711
            KeyResult.target_value > 0,
            KeyResult.target_date != None,  # noqa: E711
            KeyResult.target_date <= deadline_cutoff,
        )
        .limit(10)
    )
    for kr in kr_result.scalars().all():
        progress_ratio = kr.current_value / kr.target_value
        if progress_ratio < _KR_BEHIND_THRESHOLD:
            warnings.append({
                "kind": "kr_behind",
                "key_result_id": kr.id,
                "objective_id": kr.objective_id,
                "title": kr.title,
                "current_value": kr.current_value,
                "target_value": kr.target_value,
                "unit": kr.unit,
                "progress_pct": round(progress_ratio * 100, 1),
                "target_date": kr.target_date.isoformat(),
            })

    # 4. High-priority pending reminders due today (task_deadline, streak_warning, calendar_prep)
    day_end = datetime(today.year, today.month, today.day, 23, 59, 59)
    reminder_result = await session.execute(
        select(ScheduledReminder)
        .where(
            ScheduledReminder.user_id == user_id,
            ScheduledReminder.status == "pending",
            ScheduledReminder.scheduled_for <= day_end,
            ScheduledReminder.reminder_type.in_(_HIGH_PRIORITY_REMINDER_TYPES),
        )
        .order_by(ScheduledReminder.scheduled_for)
        .limit(5)
    )
    for rem in reminder_result.scalars().all():
        warnings.append({
            "kind": "pending_reminder",
            "reminder_id": rem.id,
            "reminder_type": rem.reminder_type,
            "message": rem.message,
            "scheduled_for": rem.scheduled_for.isoformat(),
        })

    return warnings


async def _build_goal_slots_for_today(
    session: AsyncSession,
    user_id: int,
    today: date,
) -> list[dict]:
    """CORE-6: Derive today's free-slot suggestions from active objectives/KRs.

    Surfaces daily and weekly KR cadences as suggested work blocks so the
    morning brief and evening review include goal-pipeline context alongside
    regular tasks.
    """
    obj_result = await session.execute(
        select(Objective)
        .where(
            Objective.user_id == user_id,
            Objective.status == "active",
        )
        .order_by(Objective.priority_weight.desc())
        .limit(5)
    )
    objectives = obj_result.scalars().all()

    suggestions: list[dict] = []
    for obj in objectives:
        kr_result = await session.execute(
            select(KeyResult).where(
                KeyResult.objective_id == obj.id,
                KeyResult.status == "active",
                KeyResult.frequency.in_(["daily", "weekly"]),
            )
        )
        for kr in kr_result.scalars().all()[:2]:  # cap per objective
            suggestions.append({
                "type": "goal_slot",
                "objective_id": obj.id,
                "objective_title": obj.title,
                "key_result_id": kr.id,
                "title": kr.title,
                "frequency": kr.frequency,
                "suggested_date": today.isoformat(),
            })
        if len(suggestions) >= 3:
            break

    return suggestions
