"""Context builder — loads user data from DB for the AI prompt."""
from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from bot.database.models import (
    Conversation, KeyResult, Log, Objective, Routine, RoutineCompletion, Task, User,
)


async def build_context(session: AsyncSession, user: User) -> str:
    """Build a rich context string for the AI prompt."""
    today = date.today()
    lines: list[str] = []

    # Active objectives with key results
    obj_result = await session.execute(
        select(Objective)
        .options(selectinload(Objective.key_results))
        .where(
            and_(Objective.user_id == user.id, Objective.status == "active")
        )
        .order_by(Objective.created_at)
    )
    objectives = obj_result.scalars().all()

    if objectives:
        lines.append("=== AKTIVE ZIELE (OKRs) ===")
        for obj in objectives:
            lines.append(f"\n🎯 {obj.title} [{obj.category}]")
            if obj.target_date:
                lines.append(f"   Zieldatum: {obj.target_date}")
            for kr in obj.key_results:
                if kr.status == "active":
                    progress = ""
                    if kr.target_value and kr.target_value > 0:
                        pct = int((kr.current_value / kr.target_value) * 100)
                        progress = f" ({pct}% — {kr.current_value}/{kr.target_value} {kr.unit or ''})"
                    lines.append(f"   📊 KR#{kr.id}: {kr.title}{progress} [{kr.frequency}]")
        lines.append("")

    # Today's open tasks (top 5 by priority)
    task_result = await session.execute(
        select(Task)
        .where(
            and_(
                Task.user_id == user.id,
                Task.status.in_(["todo", "in_progress"]),
            )
        )
        .order_by(Task.priority.desc(), Task.due_date.asc().nulls_last())
        .limit(5)
    )
    tasks = task_result.scalars().all()
    if tasks:
        lines.append("=== OFFENE TASKS (Top 5) ===")
        for t in tasks:
            due = f" [fällig: {t.due_date}]" if t.due_date else ""
            overdue = " ⚠️ ÜBERFÄLLIG" if t.due_date and t.due_date < today else ""
            lines.append(f"  #{t.id} [{t.priority}★] {t.title}{due}{overdue}")
        lines.append("")

    # Today's routines and completions
    routine_result = await session.execute(
        select(Routine).where(
            and_(Routine.user_id == user.id, Routine.status == "active")
        )
    )
    routines = routine_result.scalars().all()
    if routines:
        completed_today_result = await session.execute(
            select(RoutineCompletion.routine_id).where(
                and_(
                    RoutineCompletion.user_id == user.id,
                    RoutineCompletion.completed_at >= datetime.combine(today, datetime.min.time()),
                )
            )
        )
        completed_ids = set(completed_today_result.scalars().all())

        lines.append("=== ROUTINEN HEUTE ===")
        for r in routines:
            status = "✅" if r.id in completed_ids else "☐"
            lines.append(f"  {status} #{r.id}: {r.title} ({r.frequency_human})")
        lines.append("")

    # Recent logs (last 10)
    log_result = await session.execute(
        select(Log)
        .where(Log.user_id == user.id)
        .order_by(Log.created_at.desc())
        .limit(10)
    )
    logs = log_result.scalars().all()
    if logs:
        lines.append("=== LETZTE LOGS ===")
        for log in logs:
            ts = log.logged_at.strftime("%d.%m %H:%M")
            if log.log_type == "workout":
                d = log.data
                exercise = d.get("exercise", "?")
                weight = d.get("weight", "")
                reps = d.get("reps", "")
                sets = d.get("sets", "")
                detail = f"{exercise} {weight}kg×{reps}×{sets}Sätze" if weight else exercise
                lines.append(f"  [{ts}] 💪 Workout: {detail}")
            elif log.log_type == "water":
                lines.append(f"  [{ts}] 💧 Wasser: {log.data.get('amount', '?')}L")
            elif log.log_type == "mood":
                lines.append(f"  [{ts}] 😊 Mood: {log.data.get('score', '?')}/10 — {log.data.get('notes', '')}")
            elif log.log_type == "progress":
                lines.append(f"  [{ts}] 📈 Progress: {log.data.get('description', '')} (KR#{log.key_result_id})")
            else:
                lines.append(f"  [{ts}] 📝 {log.log_type}: {log.raw_input or str(log.data)[:80]}")
        lines.append("")

    # Today's water total
    water_result = await session.execute(
        select(Log).where(
            and_(
                Log.user_id == user.id,
                Log.log_type == "water",
                Log.logged_at >= datetime.combine(today, datetime.min.time()),
            )
        )
    )
    water_logs = water_result.scalars().all()
    if water_logs:
        total = sum(l.data.get("amount", 0) for l in water_logs)
        lines.append(f"💧 Wasser heute: {total:.1f}L")
        lines.append("")

    # Last 5 conversation turns
    conv_result = await session.execute(
        select(Conversation)
        .where(Conversation.user_id == user.id)
        .order_by(Conversation.created_at.desc())
        .limit(5)
    )
    conversations = list(reversed(conv_result.scalars().all()))
    if conversations:
        lines.append("=== LETZTE UNTERHALTUNG ===")
        for c in conversations:
            role_label = "Du" if c.role == "user" else "OS"
            lines.append(f"  {role_label}: {c.content[:120]}")
        lines.append("")

    if not lines:
        return "Noch keine Daten. Der User ist neu — hilf ihm, sein erstes Ziel anzulegen."

    return "\n".join(lines)
