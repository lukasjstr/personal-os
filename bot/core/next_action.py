"""Sprint 5: /next command — smart single best next action with inline done/skip buttons."""
import logging
from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup

from bot.database.models import DailyContext, KeyResult, Objective, Task, User
from bot.telegram.sender import send_message

logger = logging.getLogger(__name__)

PRIORITY_WEIGHTS = {
    1: 50,
    2: 35,
    3: 20,
    4: 10,
    5: 5,
}

ENERGY_MATCH = {
    # task priority → energy levels that match well
    1: {8, 9, 10},   # high-priority task → needs high energy
    2: {6, 7, 8, 9, 10},
    3: {4, 5, 6, 7, 8},
    4: {1, 2, 3, 4, 5, 6},
    5: {1, 2, 3, 4, 5},
}


async def _get_today_context(session: AsyncSession, user_id: int) -> Optional[DailyContext]:
    today = date.today()
    res = await session.execute(
        select(DailyContext).where(
            and_(DailyContext.user_id == user_id, DailyContext.date == today)
        )
    )
    return res.scalar_one_or_none()


def _score_task(task: Task, ctx: Optional[DailyContext], today: date) -> float:
    score = PRIORITY_WEIGHTS.get(task.priority, 20)

    # Deadline urgency bonus
    if task.due_date:
        days_until = (task.due_date - today).days
        if days_until < 0:
            score += 40  # overdue
        elif days_until == 0:
            score += 30
        elif days_until <= 2:
            score += 20
        elif days_until <= 7:
            score += 10

    # Energy match bonus
    if ctx and ctx.energy:
        if ctx.energy in ENERGY_MATCH.get(task.priority, set()):
            score += 8

    # Low-energy day adjustment (set by action_engine)
    if ctx and ctx.daily_plan and ctx.daily_plan.get("low_energy_day"):
        if task.priority >= 4:
            score += 15  # boost easy tasks
        elif task.priority <= 1:
            score -= 10  # penalize hard tasks

    # Older tasks get slight boost (avoid starvation)
    if task.created_at:
        age_days = (datetime.utcnow() - task.created_at).days
        score += min(age_days * 0.5, 10)

    return score


async def get_next_action(
    session: AsyncSession,
    user: User,
) -> Optional[dict]:
    """Return the single best next task with context for display.

    Returns dict with:
      task_id, title, objective_title, kr_title, priority, due_date,
      reason, energy_match
    """
    today = date.today()
    ctx = await _get_today_context(session, user.id)

    # Load open tasks with their objective/KR
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
    )
    tasks = task_res.scalars().all()

    if not tasks:
        return None

    # Score and pick best
    scored = [(t, _score_task(t, ctx, today)) for t in tasks]
    scored.sort(key=lambda x: x[1], reverse=True)
    best_task, best_score = scored[0]

    # Build reason string
    reason_parts = []

    if best_task.priority == 1:
        reason_parts.append("höchste Priorität")
    elif best_task.priority == 2:
        reason_parts.append("hohe Priorität")

    if best_task.due_date:
        days_until = (best_task.due_date - today).days
        if days_until < 0:
            reason_parts.append(f"überfällig seit {abs(days_until)} Tag(en)")
        elif days_until == 0:
            reason_parts.append("heute fällig")
        elif days_until <= 2:
            reason_parts.append(f"fällig in {days_until} Tag(en)")

    if ctx and ctx.energy and ctx.energy in ENERGY_MATCH.get(best_task.priority, set()):
        reason_parts.append(f"passt zu deiner Energie ({ctx.energy}/10)")

    if best_task.objective:
        reason_parts.append(f"gehört zu '{best_task.objective.title[:40]}'")

    reason = " · ".join(reason_parts) if reason_parts else "beste verfügbare Option"

    return {
        "task_id": best_task.id,
        "title": best_task.title,
        "objective_title": best_task.objective.title if best_task.objective else None,
        "kr_title": best_task.key_result.title if best_task.key_result else None,
        "priority": best_task.priority,
        "due_date": best_task.due_date.isoformat() if best_task.due_date else None,
        "reason": reason,
        "score": round(best_score, 1),
        "total_open": len(tasks),
    }


async def send_next_action(bot: Bot, user: User, session: AsyncSession) -> None:
    """Send the /next action message with inline done/skip buttons."""
    action = await get_next_action(session, user)

    if not action:
        await bot.send_message(
            chat_id=user.telegram_id,
            text="✅ Keine offenen Tasks! Du bist auf dem neuesten Stand.",
        )
        return

    lines = [f"⚡ *Dein nächster Schritt:*\n"]
    lines.append(f"*{action['title']}*")

    if action["objective_title"]:
        if action["kr_title"]:
            lines.append(f"📎 {action['objective_title']} → {action['kr_title']}")
        else:
            lines.append(f"📎 {action['objective_title']}")

    if action["due_date"]:
        lines.append(f"📅 Fällig: {action['due_date']}")

    lines.append(f"\n💡 _{action['reason']}_")
    lines.append(f"\n_{action['total_open']} offene Tasks insgesamt_")

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Erledigt", callback_data=f"next_done_{action['task_id']}"),
            InlineKeyboardButton("⏭ Überspringen", callback_data=f"next_skip_{action['task_id']}"),
        ]
    ])

    await bot.send_message(
        chat_id=user.telegram_id,
        text="\n".join(lines),
        parse_mode="Markdown",
        reply_markup=keyboard,
    )


async def handle_next_done(bot: Bot, user: User, session: AsyncSession, task_id: int) -> None:
    """Mark task as done, award XP, send confirmation."""
    task_res = await session.execute(
        select(Task).where(and_(Task.id == task_id, Task.user_id == user.id))
    )
    task = task_res.scalar_one_or_none()
    if not task:
        await bot.send_message(chat_id=user.telegram_id, text="❌ Task nicht gefunden.")
        return

    task.status = "done"
    task.completed_at = datetime.utcnow()

    # Award XP
    xp_gain = max(5, 10 - (task.priority - 1) * 2)
    user.xp = (user.xp or 0) + xp_gain
    await session.commit()

    # Offer next action
    next_action = await get_next_action(session, user)
    if next_action:
        lines = [
            f"✅ *'{task.title}'* erledigt! +{xp_gain} XP\n",
            f"👉 *Nächster Schritt:* {next_action['title']}",
        ]
        if next_action["objective_title"]:
            lines.append(f"📎 {next_action['objective_title']}")
        lines.append(f"💡 _{next_action['reason']}_")

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Erledigt", callback_data=f"next_done_{next_action['task_id']}"),
                InlineKeyboardButton("⏭ Überspringen", callback_data=f"next_skip_{next_action['task_id']}"),
            ]
        ])
        await bot.send_message(
            chat_id=user.telegram_id,
            text="\n".join(lines),
            parse_mode="Markdown",
            reply_markup=keyboard,
        )
    else:
        await bot.send_message(
            chat_id=user.telegram_id,
            text=f"✅ *'{task.title}'* erledigt! +{xp_gain} XP\n\n🎉 Alle Tasks abgehakt!",
            parse_mode="Markdown",
        )


async def handle_next_skip(bot: Bot, user: User, session: AsyncSession, task_id: int) -> None:
    """Skip current task and show the next one."""
    task_res = await session.execute(
        select(Task).where(and_(Task.id == task_id, Task.user_id == user.id))
    )
    task = task_res.scalar_one_or_none()
    skipped_title = task.title if task else "Task"

    # Get next excluding this task
    today = date.today()
    ctx = await _get_today_context(session, user.id)
    task_res2 = await session.execute(
        select(Task)
        .options(selectinload(Task.objective), selectinload(Task.key_result))
        .where(and_(
            Task.user_id == user.id,
            Task.status.in_(["todo", "in_progress"]),
            Task.category != "shopping",
            Task.id != task_id,
        ))
    )
    tasks = task_res2.scalars().all()

    if not tasks:
        await bot.send_message(
            chat_id=user.telegram_id,
            text=f"⏭ '{skipped_title}' übersprungen.\n\n✅ Keine weiteren Tasks!",
        )
        return

    scored = [(t, _score_task(t, ctx, today)) for t in tasks]
    scored.sort(key=lambda x: x[1], reverse=True)
    best_task, _ = scored[0]

    reason_parts = []
    if best_task.priority <= 2:
        reason_parts.append("hohe Priorität")
    if best_task.objective:
        reason_parts.append(f"gehört zu '{best_task.objective.title[:40]}'")
    reason = " · ".join(reason_parts) or "nächste verfügbare Option"

    lines = [
        f"⏭ Übersprungen: _{skipped_title}_\n",
        f"⚡ *Nächster Schritt:*",
        f"*{best_task.title}*",
    ]
    if best_task.objective:
        lines.append(f"📎 {best_task.objective.title}")
    lines.append(f"💡 _{reason}_")

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Erledigt", callback_data=f"next_done_{best_task.id}"),
            InlineKeyboardButton("⏭ Überspringen", callback_data=f"next_skip_{best_task.id}"),
        ]
    ])
    await bot.send_message(
        chat_id=user.telegram_id,
        text="\n".join(lines),
        parse_mode="Markdown",
        reply_markup=keyboard,
    )
