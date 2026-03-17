"""Autopilot Planner — auto-generates Top-5 tasks each morning.

The system (not the user) selects the 5 most important tasks based on:
- KR progress (lagging KRs get priority)
- Task due dates and priority
- Today's energy (from DailyContext if available)
- Routine adherence

This replaces the manual "Top-5 Tasks priorisieren" routine.
"""
import logging
from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from bot.database.models import DailyContext, KeyResult, Objective, Task, User

logger = logging.getLogger(__name__)


async def generate_top5(
    session: AsyncSession,
    user: User,
    target_date: Optional[date] = None,
) -> list[dict]:
    """Auto-select top-5 tasks for today.

    Scoring factors:
    - Task priority (P1=50, P2=35, P3=20, P4=10, P5=5)
    - Due date urgency (overdue=+40, today=+30, 2 days=+20, week=+10)
    - KR lag bonus: if the linked KR is behind target, +20
    - No KR linked: small penalty (-5) — we prefer tasks tied to measurable KRs

    Returns list of dicts with task info + reason.
    """
    if target_date is None:
        target_date = date.today()

    # Load open tasks
    task_res = await session.execute(
        select(Task)
        .options(
            selectinload(Task.objective),
            selectinload(Task.key_result),
        )
        .where(and_(
            Task.user_id == user.id,
            Task.status.in_(["todo", "in_progress"]),
            Task.category != "shopping",
        ))
        .order_by(Task.priority.asc(), Task.due_date.asc().nulls_last())
    )
    tasks = task_res.scalars().all()

    if not tasks:
        return []

    # Get today's energy context
    ctx_res = await session.execute(
        select(DailyContext).where(and_(
            DailyContext.user_id == user.id,
            DailyContext.date == target_date,
        ))
    )
    ctx = ctx_res.scalar_one_or_none()
    energy = ctx.energy if ctx else None

    # Compute KR lag scores
    kr_lag: dict[int, float] = {}
    kr_res = await session.execute(
        select(KeyResult).where(and_(
            KeyResult.user_id == user.id,
            KeyResult.status == "active",
        ))
    )
    for kr in kr_res.scalars().all():
        if kr.target_value and kr.target_value > 0:
            progress_pct = (kr.current_value or 0) / kr.target_value
            # If behind 50%+ we prioritize tasks linked to this KR
            if progress_pct < 0.5:
                kr_lag[kr.id] = 20
            elif progress_pct < 0.25:
                kr_lag[kr.id] = 35
        else:
            kr_lag[kr.id] = 0

    PRIORITY_SCORE = {1: 50, 2: 35, 3: 20, 4: 10, 5: 5}

    scored = []
    for task in tasks:
        score = PRIORITY_SCORE.get(task.priority, 20)

        # Due date urgency
        if task.due_date:
            days_until = (task.due_date - target_date).days
            if days_until < 0:
                score += 40
            elif days_until == 0:
                score += 30
            elif days_until <= 2:
                score += 20
            elif days_until <= 7:
                score += 10

        # KR lag bonus
        if task.key_result_id:
            score += kr_lag.get(task.key_result_id, 0)
        else:
            score -= 5  # slight preference for KR-linked tasks

        # Energy match (high energy → tackle hard tasks P1/P2)
        if energy:
            if energy >= 7 and task.priority <= 2:
                score += 8
            elif energy <= 4 and task.priority >= 3:
                score += 5  # easy tasks on low-energy days

        # Build reason
        reasons = []
        if task.priority == 1:
            reasons.append("höchste Priorität")
        if task.due_date:
            days_until = (task.due_date - target_date).days
            if days_until < 0:
                reasons.append(f"überfällig")
            elif days_until == 0:
                reasons.append("heute fällig")
            elif days_until <= 2:
                reasons.append(f"in {days_until} Tagen fällig")
        if task.key_result_id and kr_lag.get(task.key_result_id, 0) > 0:
            reasons.append("KR liegt zurück")
        if task.objective:
            reasons.append(f"→ {task.objective.title[:35]}")

        scored.append({
            "task_id": task.id,
            "title": task.title,
            "priority": task.priority,
            "objective_title": task.objective.title if task.objective else None,
            "kr_title": task.key_result.title if task.key_result else None,
            "due_date": task.due_date.isoformat() if task.due_date else None,
            "score": round(score, 1),
            "reason": " · ".join(reasons) if reasons else "offene Aufgabe",
        })

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:5]


def format_top5_for_telegram(top5: list[dict]) -> str:
    """Format top-5 list for Telegram message."""
    if not top5:
        return "✅ Keine offenen Tasks — alles erledigt!"

    PRIORITY_EMOJI = {1: "🔴", 2: "🟠", 3: "🟡", 4: "🟢", 5: "⚪"}
    lines = ["⚡ *Deine Top-5 für heute:*\n"]
    for i, t in enumerate(top5, 1):
        emoji = PRIORITY_EMOJI.get(t["priority"], "•")
        lines.append(f"{i}. {emoji} *{t['title']}*")
        if t["reason"]:
            lines.append(f"   _{t['reason']}_")
    return "\n".join(lines)
