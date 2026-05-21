"""V3 P06 — Evening review score + harter Punkt (deterministic, no AI).

Used by bot/jobs/evening_review.py to build the fixed-template review.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import DailyBrief, RoutineCompletion, Task

logger = logging.getLogger(__name__)


async def calculate_daily_score(
    session: AsyncSession, user_id: int, today: date
) -> dict:
    """Return a deterministic day-score + breakdown for the evening review.

    Returns:
        {
          "score": int,                    # 0-10
          "delivered": {"tasks": int, "routines": int},
          "missed_must": list[str],        # titles from morning brief that weren't done
          "best_thing": Optional[str],     # highest-priority task that got done
          "harter_punkt": str,             # 1 confrontational line, never empty
          "tomorrow_top": Optional[str],   # title of highest-priority open task
        }
    Returns score=0 and empty fields if no morning brief exists.
    """
    brief = await _get_daily_brief(session, user_id, today)
    if brief is None or not (brief.priorities or []):
        # No plan today → degenerate review
        delivered_tasks, delivered_routines = await _count_completions(session, user_id, today)
        return {
            "score": min(10, delivered_tasks + delivered_routines),
            "delivered": {"tasks": delivered_tasks, "routines": delivered_routines},
            "missed_must": [],
            "best_thing": None,
            "harter_punkt": "Kein Morgen-Brief war heute aktiv. Setze morgen früh den Anker.",
            "tomorrow_top": await _tomorrow_top_title(session, user_id),
        }

    morning_priorities = brief.priorities or []
    delivered: list[str] = []
    missed: list[str] = []
    delivered_task_priorities: list[int] = []

    for p in morning_priorities:
        if not isinstance(p, dict):
            continue
        pid = p.get("id")
        ptitle = str(p.get("title") or "")
        if not ptitle:
            continue
        if isinstance(pid, int):
            # Real Task
            task = await session.get(Task, pid)
            if (task is not None and task.status == "done"
                    and task.completed_at is not None
                    and task.completed_at.date() == today):
                delivered.append(ptitle)
                delivered_task_priorities.append(task.priority or 5)
                continue
        # Protocol pseudo-items (type=protocol) — count as delivered if any
        # routine in that bucket completed today. Best-effort heuristic.
        if p.get("type") == "protocol":
            # We don't model this fully; assume completed if anything happened today.
            delivered_tasks, delivered_routines = await _count_completions(session, user_id, today)
            if delivered_routines > 0 or delivered_tasks > 0:
                delivered.append(ptitle)
                continue
        missed.append(ptitle)

    delivered_total = len(delivered)
    delivered_tasks_today, delivered_routines_today = await _count_completions(
        session, user_id, today
    )
    surprise_tasks = max(0, delivered_tasks_today - delivered_total)

    completion_rate = delivered_total / max(1, len(morning_priorities))
    score = int(round(completion_rate * 8)) + min(2, surprise_tasks)
    score = max(0, min(10, score))

    best_thing: Optional[str] = None
    if delivered:
        # Find the highest-priority delivered task title
        idx = delivered_task_priorities.index(min(delivered_task_priorities)) if delivered_task_priorities else 0
        best_thing = delivered[min(idx, len(delivered) - 1)]

    harter_punkt = await generate_harter_punkt(session, user_id, today, missed)
    tomorrow_top = await _tomorrow_top_title(session, user_id)

    return {
        "score": score,
        "delivered": {"tasks": delivered_tasks_today, "routines": delivered_routines_today},
        "missed_must": missed,
        "best_thing": best_thing,
        "harter_punkt": harter_punkt,
        "tomorrow_top": tomorrow_top,
    }


async def generate_harter_punkt(
    session: AsyncSession, user_id: int, today: date, missed_today: list[str]
) -> str:
    """One confrontational line. Priority:
      1. Same task missed 3+ days in a row → "Erste-Aktion-des-Tages oder weg damit."
      2. Week brief completion rate < 50% → "Versprechensdisziplin ist Kompetenz #6."
      3. Some missed today → "N Muss-Tasks gestern verschoben. Was war im Weg?"
      4. Everything delivered → positive but sharp.
    """
    # 1) Repeating misses across last 3 daily briefs
    repeating = await _find_repeatedly_missed(session, user_id, today, lookback=3)
    if repeating:
        title, days = repeating
        return (
            f"'{title}' wurde {days} Tage verschoben. "
            f"Morgen Erste-Aktion-des-Tages oder weg damit."
        )

    # 2) Last 7-day brief completion rate
    rate = await _week_completion_rate(session, user_id, today)
    if rate is not None and rate < 0.5:
        pct = int(rate * 100)
        return (
            f"Diese Woche {pct}% Morgen-Prios geliefert. "
            f"Versprechensdisziplin ist Kompetenz #6 — heute notiert."
        )

    # 3) Some missed today
    if missed_today:
        return f"{len(missed_today)} Muss-Tasks heute verschoben. Was war im Weg?"

    # 4) Clean day
    return "Heute alle Muss-Tasks geliefert. Halte das Tempo morgen oder erhöhe."


# ─── helpers ──────────────────────────────────────────────────────────────────


async def _get_daily_brief(session: AsyncSession, user_id: int, today: date) -> Optional[DailyBrief]:
    return (await session.execute(
        select(DailyBrief).where(and_(
            DailyBrief.user_id == user_id,
            DailyBrief.brief_date == today,
        ))
    )).scalar_one_or_none()


async def _count_completions(
    session: AsyncSession, user_id: int, today: date
) -> tuple[int, int]:
    today_start = datetime.combine(today, datetime.min.time())
    today_end = datetime.combine(today, datetime.max.time())
    done_tasks = (await session.execute(
        select(Task).where(and_(
            Task.user_id == user_id,
            Task.status == "done",
            Task.completed_at >= today_start,
            Task.completed_at <= today_end,
            Task.category != "shopping",
        ))
    )).scalars().all()
    done_routines = (await session.execute(
        select(RoutineCompletion).where(and_(
            RoutineCompletion.user_id == user_id,
            RoutineCompletion.completed_at >= today_start,
            RoutineCompletion.completed_at <= today_end,
        ))
    )).scalars().all()
    return len(done_tasks), len(done_routines)


async def _find_repeatedly_missed(
    session: AsyncSession, user_id: int, today: date, lookback: int = 3
) -> Optional[tuple[str, int]]:
    """If the SAME priority title appears in ≥`lookback` recent daily briefs AND the
    task with that title is still in TODO state, return (title, count). Else None."""
    since = today - timedelta(days=lookback + 2)
    briefs = (await session.execute(
        select(DailyBrief).where(and_(
            DailyBrief.user_id == user_id,
            DailyBrief.brief_date >= since,
            DailyBrief.brief_date <= today,
        )).order_by(DailyBrief.brief_date.asc())
    )).scalars().all()

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

    for title, n in sorted(counts.items(), key=lambda kv: -kv[1]):
        if n < lookback:
            break
        still_open = (await session.execute(
            select(Task).where(and_(
                Task.user_id == user_id,
                Task.title == title,
                Task.status.in_(["todo", "in_progress"]),
            )).limit(1)
        )).scalar_one_or_none()
        if still_open is not None:
            return title, n
    return None


async def _week_completion_rate(
    session: AsyncSession, user_id: int, today: date
) -> Optional[float]:
    """Return ratio of delivered morning-brief priorities over the last 7 days."""
    since = today - timedelta(days=6)
    briefs = (await session.execute(
        select(DailyBrief).where(and_(
            DailyBrief.user_id == user_id,
            DailyBrief.brief_date >= since,
            DailyBrief.brief_date <= today,
        ))
    )).scalars().all()
    if not briefs:
        return None
    total = 0
    delivered = 0
    for b in briefs:
        prios = b.priorities or []
        for p in prios:
            if not isinstance(p, dict):
                continue
            total += 1
            pid = p.get("id")
            if isinstance(pid, int):
                task = await session.get(Task, pid)
                if (task is not None and task.status == "done"
                        and task.completed_at is not None
                        and task.completed_at.date() <= today):
                    delivered += 1
    if total == 0:
        return None
    return delivered / total


async def _tomorrow_top_title(session: AsyncSession, user_id: int) -> Optional[str]:
    top = (await session.execute(
        select(Task).where(and_(
            Task.user_id == user_id,
            Task.status.in_(["todo", "in_progress"]),
            Task.category != "shopping",
        )).order_by(Task.priority.asc(), Task.due_date.asc().nulls_last()).limit(1)
    )).scalar_one_or_none()
    return top.title if top else None
