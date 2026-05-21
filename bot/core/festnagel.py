"""V3 P05 — Festnagel generator: ONE confrontational line per morning brief.

Deterministic, no AI. Uses real data from the last 7-30 days.

Priority order (first match wins):
  1. Weekly KR under 50% target with <2 days left
  2. Stale objective (no log on any KR for ≥7 days)
  3. Recent skipped 'must' tasks (3+ days of missed morning-brief priorities)
  4. Fallback line — never empty.

Returns the line as a plain string (no markdown headers — those are added
by the brief template).
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import DailyBrief, KeyResult, Log, Objective, Task

logger = logging.getLogger(__name__)


async def _kr_progress_this_week(
    session: AsyncSession, user_id: int, kr_id: int, week_start: date
) -> int:
    """Sum of log.data.value (best-effort) for this KR since week_start."""
    week_start_dt = datetime.combine(week_start, datetime.min.time())
    result = await session.execute(
        select(Log).where(and_(
            Log.user_id == user_id,
            Log.key_result_id == kr_id,
            Log.logged_at >= week_start_dt,
        ))
    )
    total = 0
    for log in result.scalars().all():
        v = (log.data or {}).get("value")
        try:
            total += int(float(v))
        except (TypeError, ValueError):
            total += 1  # one entry counts as 1 if no value
    return total


async def _candidate_weekly_kr(
    session: AsyncSession, user_id: int, today: date
) -> Optional[str]:
    """A weekly KR is at risk if <50% of target with <2 days left in week."""
    weekday = today.weekday()  # Mon=0..Sun=6
    week_start = today - timedelta(days=weekday)
    days_left = 6 - weekday  # days remaining including today

    krs = (await session.execute(
        select(KeyResult).where(and_(
            KeyResult.user_id == user_id,
            KeyResult.status == "active",
            KeyResult.frequency == "weekly",
        ))
    )).scalars().all()

    worst: Optional[tuple[float, str, int, float]] = None  # (ratio, title, completed, target)
    for kr in krs:
        if not kr.target_value or kr.target_value <= 0:
            continue
        completed = await _kr_progress_this_week(session, user_id, kr.id, week_start)
        target = float(kr.target_value)
        ratio = completed / target if target > 0 else 1.0
        if ratio < 0.5:
            if worst is None or ratio < worst[0]:
                worst = (ratio, kr.title, completed, target)

    if worst is None:
        return None

    _, title, completed, target = worst
    if days_left <= 1:
        return f"{title}: {completed}/{int(target)} diese Woche. Heute oder es kippt."
    return f"{title}: {completed}/{int(target)} diese Woche. Noch {days_left} Tage."


async def _candidate_stale_objective(
    session: AsyncSession, user_id: int, today: date, threshold_days: int = 7
) -> Optional[str]:
    """Active objective whose KRs have no log entries for `threshold_days`+ days."""
    objs = (await session.execute(
        select(Objective).where(and_(
            Objective.user_id == user_id,
            Objective.status == "active",
        ))
    )).scalars().all()

    stalest: Optional[tuple[int, Objective]] = None  # (days_stale, obj)
    for obj in objs:
        last_log = (await session.execute(
            select(func.max(Log.logged_at))
            .join(KeyResult, Log.key_result_id == KeyResult.id)
            .where(KeyResult.objective_id == obj.id)
        )).scalar()
        if last_log is None:
            # No log ever — use objective updated_at as fallback signal
            ref = obj.updated_at or obj.created_at
            if ref is None:
                continue
            days_stale = (today - ref.date()).days
        else:
            days_stale = (today - last_log.date()).days
        if days_stale >= threshold_days:
            if stalest is None or days_stale > stalest[0]:
                stalest = (days_stale, obj)

    if stalest is None:
        return None
    days_stale, obj = stalest
    return f"OBJ#{obj.id} {obj.title}: {days_stale} Tage ohne Progress. Heute ein Schritt."


async def _candidate_repeated_misses(
    session: AsyncSession, user_id: int, today: date
) -> Optional[str]:
    """If user missed their morning-brief 'must' priorities 3 days in a row,
    name the task that keeps slipping."""
    since = today - timedelta(days=5)
    briefs = (await session.execute(
        select(DailyBrief).where(and_(
            DailyBrief.user_id == user_id,
            DailyBrief.brief_date >= since,
            DailyBrief.brief_date < today,
        )).order_by(DailyBrief.brief_date.asc())
    )).scalars().all()

    # Count how many times each priority title appears across briefs
    counts: dict[str, int] = {}
    for b in briefs:
        seen: set[str] = set()
        for p in (b.priorities or []):
            if not isinstance(p, dict):
                continue
            title = str(p.get("title") or "").strip()
            if not title or title in seen:
                continue
            seen.add(title)
            counts[title] = counts.get(title, 0) + 1

    # Any task that appeared in 3+ daily briefs but is still in TODO state?
    for title, n in sorted(counts.items(), key=lambda kv: -kv[1]):
        if n < 3:
            break
        still_open = (await session.execute(
            select(Task).where(and_(
                Task.user_id == user_id,
                Task.title == title,
                Task.status.in_(["todo", "in_progress"]),
            )).limit(1)
        )).scalar_one_or_none()
        if still_open is not None:
            return f"'{title}' wurde {n} Tage verschoben. Heute Erste-Aktion oder weg damit."
    return None


def _fallback(today: date) -> str:
    weekday = today.weekday()  # Mon=0..Sun=6
    if weekday >= 5:  # Sa, So
        return "Wochenende. Kein Operatives. Eine Stunde Solitude für die kommende Woche."
    if weekday in (2, 3):  # Mi, Do
        return "Mid-Week. Was hast du Mo+Di gestrichen? Hol es heute zurück oder cut es endgültig."
    return "Tag ist offen. Nimm einen Slot vor 11:00 für das Wichtigste."


async def generate_festnagel(session: AsyncSession, user_id: int, today: Optional[date] = None) -> str:
    """Return ONE confrontational line for today's brief. Never empty."""
    if today is None:
        today = date.today()

    try:
        line = await _candidate_weekly_kr(session, user_id, today)
        if line:
            return line
        line = await _candidate_stale_objective(session, user_id, today)
        if line:
            return line
        line = await _candidate_repeated_misses(session, user_id, today)
        if line:
            return line
    except Exception:
        logger.exception("Festnagel candidate generation failed — using fallback")

    return _fallback(today)


async def generate_brief_status(
    session: AsyncSession, user_id: int, today: date
) -> dict:
    """Status block: count of active objectives + KRs at risk this week.

    Returns:
      {"active_objectives": int, "krs_at_risk": int, "energy": Optional[int]}
    """
    active_objs = (await session.execute(
        select(func.count()).select_from(Objective).where(and_(
            Objective.user_id == user_id,
            Objective.status == "active",
        ))
    )).scalar() or 0

    # KRs at risk: weekly KRs <50% this week
    weekday = today.weekday()
    week_start = today - timedelta(days=weekday)
    krs = (await session.execute(
        select(KeyResult).where(and_(
            KeyResult.user_id == user_id,
            KeyResult.status == "active",
            KeyResult.frequency == "weekly",
        ))
    )).scalars().all()
    krs_at_risk = 0
    for kr in krs:
        if not kr.target_value or kr.target_value <= 0:
            continue
        done = await _kr_progress_this_week(session, user_id, kr.id, week_start)
        if done / float(kr.target_value) < 0.5:
            krs_at_risk += 1

    # Yesterday's energy from sleep / mood log (best-effort)
    energy: Optional[int] = None
    yesterday_start = datetime.combine(today - timedelta(days=1), datetime.min.time())
    today_start = datetime.combine(today, datetime.min.time())
    sleep_log = (await session.execute(
        select(Log).where(and_(
            Log.user_id == user_id,
            Log.log_type == "sleep",
            Log.logged_at >= yesterday_start,
            Log.logged_at < today_start,
        )).order_by(Log.logged_at.desc()).limit(1)
    )).scalar_one_or_none()
    if sleep_log:
        try:
            hours = float(sleep_log.data.get("hours") or 0)
            if hours >= 7.5:
                energy = 8
            elif hours >= 6.5:
                energy = 6
            elif hours > 0:
                energy = 4
        except (TypeError, ValueError):
            pass

    return {
        "active_objectives": int(active_objs),
        "krs_at_risk": int(krs_at_risk),
        "energy": energy,
    }


async def generate_three_musts(
    session: AsyncSession, user_id: int, today: date
) -> list[dict]:
    """The 3 MUSS items for today: top task, top routine, top KR action.

    Returns up to 3 items: [{"kind": "task"|"routine"|"kr", "title": str, "slot": str|None}].
    """
    from bot.database.models import CalendarEvent, Routine

    musts: list[dict] = []
    today_start = datetime.combine(today, datetime.min.time())
    today_end = datetime.combine(today, datetime.max.time())

    # 1) Top task by priority (P1 first, then due date)
    top_task = (await session.execute(
        select(Task).where(and_(
            Task.user_id == user_id,
            Task.status.in_(["todo", "in_progress"]),
            Task.category != "shopping",
        )).order_by(Task.priority.asc(), Task.due_date.asc().nulls_last()).limit(1)
    )).scalar_one_or_none()
    if top_task is not None:
        # See if there's a calendar slot linked to this task today
        slot_ev = (await session.execute(
            select(CalendarEvent).where(and_(
                CalendarEvent.user_id == user_id,
                CalendarEvent.linked_task_id == top_task.id,
                CalendarEvent.start_time >= today_start,
                CalendarEvent.start_time <= today_end,
            )).limit(1)
        )).scalar_one_or_none()
        slot = slot_ev.start_time.strftime("%H:%M") if slot_ev else None
        musts.append({"kind": "task", "id": top_task.id, "title": top_task.title, "slot": slot})

    # 2) Top routine for today (morning preferred), not yet completed
    from bot.database.models import RoutineCompletion
    completed_ids = set((await session.execute(
        select(RoutineCompletion.routine_id).where(and_(
            RoutineCompletion.user_id == user_id,
            RoutineCompletion.completed_at >= today_start,
        ))
    )).scalars().all())
    routines = (await session.execute(
        select(Routine).where(and_(
            Routine.user_id == user_id,
            Routine.status == "active",
        )).order_by(Routine.sort_order.asc(), Routine.id.asc())
    )).scalars().all()
    candidate_routine = None
    for r in routines:
        if r.id in completed_ids:
            continue
        if (r.time_of_day or "anytime").lower() in ("morning", "anytime"):
            candidate_routine = r
            break
    if candidate_routine is None:
        # Fall back to any other not-completed active routine today
        for r in routines:
            if r.id not in completed_ids:
                candidate_routine = r
                break
    if candidate_routine is not None:
        # Linked CalendarEvent today?
        slot_ev = (await session.execute(
            select(CalendarEvent).where(and_(
                CalendarEvent.user_id == user_id,
                CalendarEvent.linked_routine_id == candidate_routine.id,
                CalendarEvent.start_time >= today_start,
                CalendarEvent.start_time <= today_end,
            )).limit(1)
        )).scalar_one_or_none()
        slot = slot_ev.start_time.strftime("%H:%M") if slot_ev else None
        musts.append({
            "kind": "routine", "id": candidate_routine.id,
            "title": candidate_routine.title, "slot": slot,
        })

    # 3) Worst weekly KR — pick the same one Festnagel highlights, but as actionable item
    weekday = today.weekday()
    week_start = today - timedelta(days=weekday)
    krs = (await session.execute(
        select(KeyResult).where(and_(
            KeyResult.user_id == user_id,
            KeyResult.status == "active",
            KeyResult.frequency == "weekly",
        ))
    )).scalars().all()
    worst: Optional[tuple[float, KeyResult, int]] = None
    for kr in krs:
        if not kr.target_value or kr.target_value <= 0:
            continue
        done = await _kr_progress_this_week(session, user_id, kr.id, week_start)
        ratio = done / float(kr.target_value)
        if worst is None or ratio < worst[0]:
            worst = (ratio, kr, done)
    if worst is not None:
        ratio, kr, done = worst
        if ratio < 1.0:  # only include if not already complete
            musts.append({
                "kind": "kr", "id": kr.id,
                "title": f"+1 für KR#{kr.id} {kr.title} ({done}/{int(kr.target_value)})",
                "slot": None,
            })

    return musts[:3]


async def generate_dropout_outlook(
    session: AsyncSession, user_id: int, today: date
) -> list[str]:
    """KRs with the worst 4-week completion ratio — likely to slip today too."""
    four_weeks_ago = datetime.combine(today - timedelta(days=28), datetime.min.time())

    krs = (await session.execute(
        select(KeyResult).where(and_(
            KeyResult.user_id == user_id,
            KeyResult.status == "active",
        ))
    )).scalars().all()

    ratings: list[tuple[float, KeyResult, int]] = []
    for kr in krs:
        log_count = (await session.execute(
            select(func.count()).select_from(Log).where(and_(
                Log.user_id == user_id,
                Log.key_result_id == kr.id,
                Log.logged_at >= four_weeks_ago,
            ))
        )).scalar() or 0
        # Expected entries over 4 weeks: 4*target for weekly, 28*target for daily, 1*target for monthly
        freq = (kr.frequency or "weekly").lower()
        if freq == "daily":
            expected = 28
        elif freq == "monthly":
            expected = 1
        else:
            expected = 4
        ratio = log_count / max(1, expected)
        ratings.append((ratio, kr, log_count))

    ratings.sort(key=lambda t: t[0])
    out: list[str] = []
    for ratio, kr, n in ratings[:2]:
        if ratio < 0.5:  # only call out things that are actually drifting
            out.append(f"{kr.title}: nur {n} Einträge in 4 Wochen")
    return out
