"""Context builder — loads user data from DB for the AI prompt."""
from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from bot.database.models import (
    CalendarEvent, Conversation, KeyResult, Log,
    Objective, Routine, RoutineCompletion, Task, User,
)


async def build_context(session: AsyncSession, user: User) -> str:
    """Build a rich context string for the AI prompt (max ~2000 tokens)."""
    today = date.today()
    today_start = datetime.combine(today, datetime.min.time())
    lines: list[str] = []

    # ─── Active OKRs ──────────────────────────────────────────────────────────
    obj_result = await session.execute(
        select(Objective)
        .options(selectinload(Objective.key_results))
        .where(and_(Objective.user_id == user.id, Objective.status == "active"))
        .order_by(Objective.created_at)
    )
    objectives = obj_result.scalars().all()

    if objectives:
        lines.append("=== AKTIVE ZIELE (OKRs) ===")
        for obj in objectives:
            lines.append(f"\n🎯 Objective #{obj.id} [{obj.category.upper()}]: {obj.title}")
            if obj.target_date:
                lines.append(f"   Zieldatum: {obj.target_date}")
            for kr in obj.key_results:
                if kr.status == "active":
                    progress = ""
                    if kr.target_value and kr.target_value > 0:
                        pct = min(100, int((kr.current_value / kr.target_value) * 100))
                        progress = f" → {kr.current_value}/{kr.target_value} {kr.unit or ''} ({pct}%)"
                    lines.append(f"   📊 KR#{kr.id}: {kr.title}{progress} [{kr.frequency}]")
        lines.append("")

    # ─── Open Tasks (top 5, non-shopping) ─────────────────────────────────────
    task_result = await session.execute(
        select(Task)
        .where(and_(
            Task.user_id == user.id,
            Task.status.in_(["todo", "in_progress"]),
            Task.category != "shopping",
        ))
        .order_by(Task.priority.asc(), Task.due_date.asc().nulls_last())
        .limit(5)
    )
    tasks = task_result.scalars().all()
    if tasks:
        lines.append("=== OFFENE TASKS (Top 5) ===")
        for t in tasks:
            due = f" [fällig: {t.due_date}]" if t.due_date else ""
            overdue = " ⚠️ ÜBERFÄLLIG" if t.due_date and t.due_date < today else ""
            cat = f" [{t.category}]" if t.category != "general" else ""
            lines.append(f"  Task#{t.id} [P{t.priority}]{cat}: {t.title}{due}{overdue}")
        lines.append("")

    # ─── Shopping List ─────────────────────────────────────────────────────────
    shopping_result = await session.execute(
        select(Task)
        .where(and_(
            Task.user_id == user.id,
            Task.category == "shopping",
            Task.status == "todo",
        ))
        .order_by(Task.created_at.asc())
    )
    shopping_items = shopping_result.scalars().all()
    if shopping_items:
        lines.append(f"=== EINKAUFSLISTE ({len(shopping_items)} Items) ===")
        for s in shopping_items:
            lines.append(f"  ☐ {s.title} (Task#{s.id})")
        lines.append("")

    # ─── Today's Routines ─────────────────────────────────────────────────────
    routine_result = await session.execute(
        select(Routine).where(and_(Routine.user_id == user.id, Routine.status == "active"))
    )
    routines = routine_result.scalars().all()
    if routines:
        completed_result = await session.execute(
            select(RoutineCompletion.routine_id).where(and_(
                RoutineCompletion.user_id == user.id,
                RoutineCompletion.completed_at >= today_start,
            ))
        )
        completed_ids = set(completed_result.scalars().all())
        lines.append("=== ROUTINEN HEUTE ===")
        for r in routines:
            status = "✅" if r.id in completed_ids else "☐"
            lines.append(f"  {status} Routine#{r.id}: {r.title} ({r.frequency_human})")
        lines.append("")

    # ─── Today's Calendar Events ──────────────────────────────────────────────
    cal_result = await session.execute(
        select(CalendarEvent)
        .where(and_(
            CalendarEvent.user_id == user.id,
            CalendarEvent.start_time >= today_start,
            CalendarEvent.start_time < datetime.combine(today, datetime.max.time()),
        ))
        .order_by(CalendarEvent.start_time)
    )
    events = cal_result.scalars().all()
    if events:
        lines.append("=== TERMINE HEUTE ===")
        for e in events:
            lines.append(f"  {e.start_time.strftime('%H:%M')} {e.title}")
        lines.append("")

    # ─── Recent Logs (last 8) ─────────────────────────────────────────────────
    log_result = await session.execute(
        select(Log)
        .where(Log.user_id == user.id)
        .order_by(Log.created_at.desc())
        .limit(8)
    )
    logs = log_result.scalars().all()
    if logs:
        lines.append("=== LETZTE AKTIVITÄT ===")
        for log in logs:
            ts = log.logged_at.strftime("%d.%m %H:%M")
            if log.log_type == "workout":
                d = log.data
                exercise = d.get("exercise", "?")
                detail = exercise
                if d.get("weight"):
                    detail += f" {d['weight']}kg"
                if d.get("reps"):
                    detail += f"×{d['reps']}"
                lines.append(f"  [{ts}] 💪 Workout: {detail}")
            elif log.log_type == "water":
                lines.append(f"  [{ts}] 💧 Wasser: {log.data.get('amount', '?')}L")
            elif log.log_type == "mood":
                lines.append(f"  [{ts}] 😊 Mood: {log.data.get('score', '?')}/10")
            elif log.log_type == "food":
                lines.append(f"  [{ts}] 🍽️ Essen: {log.data.get('description', '')[:50]}")
            elif log.log_type == "progress":
                lines.append(f"  [{ts}] 📈 Progress: +{log.data.get('value', '?')} (KR#{log.key_result_id})")
            else:
                lines.append(f"  [{ts}] 📝 {log.log_type}: {log.raw_input or str(log.data)[:60]}")
        lines.append("")

    # ─── Workout Progression Memory ───────────────────────────────────────────
    # Load last 30 workout logs and build per-exercise history for progression
    workout_result = await session.execute(
        select(Log).where(and_(
            Log.user_id == user.id,
            Log.log_type == "workout",
        )).order_by(Log.logged_at.desc()).limit(30)
    )
    workout_history = list(workout_result.scalars().all())
    if workout_history:
        lines.append("=== TRAININGS-GEDÄCHTNIS (letzte Gewichte pro Übung) ===")
        seen_exercises: set[str] = set()
        for wl in workout_history:
            ex = wl.data.get("exercise", "?")
            if ex in seen_exercises:
                continue
            seen_exercises.add(ex)
            parts = [f"  {ex} [{wl.logged_at.strftime('%d.%m.%y')}]"]
            w = wl.data.get("weight")
            r = wl.data.get("reps")
            s = wl.data.get("sets")
            if w:
                parts.append(f"{w}kg")
            if s and r:
                parts.append(f"{s}×{r}")
            if w:
                next_w = round(w + 2.5, 1)
                parts.append(f"→ heute: {next_w}kg probieren")
            lines.append(" ".join(parts))
        lines.append("")

    # ─── Today's Water Total ──────────────────────────────────────────────────
    water_result = await session.execute(
        select(Log).where(and_(
            Log.user_id == user.id,
            Log.log_type == "water",
            Log.logged_at >= today_start,
        ))
    )
    water_logs = water_result.scalars().all()
    if water_logs:
        total = sum(l.data.get("amount", 0) for l in water_logs)
        lines.append(f"💧 Wasser heute gesamt: {total:.1f}L")
        lines.append("")

    # ─── Mood Trend (7 days) ──────────────────────────────────────────────────
    since_7d = datetime.utcnow() - timedelta(days=7)
    mood_result = await session.execute(
        select(Log).where(and_(
            Log.user_id == user.id,
            Log.log_type == "mood",
            Log.logged_at >= since_7d,
        )).order_by(Log.logged_at.asc())
    )
    mood_logs = mood_result.scalars().all()
    if mood_logs:
        scores = [str(l.data.get("score", "?")) for l in mood_logs]
        lines.append(f"😊 Mood (7 Tage): {', '.join(scores)}")
        lines.append("")

    # ─── Today's Fitness Split ────────────────────────────────────────────────
    try:
        from bot.core.fitness_protocol import get_today_split, load_fitness_protocol
        fitness_view = get_today_split(load_fitness_protocol(), today)
        if fitness_view.get("is_rest_day"):
            lines.append("=== FITNESS HEUTE ===")
            lines.append("  Ruhetag / aktive Regeneration")
        else:
            lines.append("=== FITNESS HEUTE ===")
            lines.append(f"  Split: {fitness_view.get('split_name')} ({fitness_view.get('focus', '')})")
            exercises = fitness_view.get("exercises", [])
            if exercises:
                lines.append(f"  Übungen: {', '.join(exercises[:6])}")
            lines.append(f"  → Trainingsblock benennen als: '💪 {fitness_view.get('split_name')}: {', '.join(exercises[:3])}'")
        lines.append("")
    except Exception:
        pass

    # ─── Health Metrics (yesterday) ───────────────────────────────────────────
    try:
        from bot.core.health_sync import get_health_context
        health_ctx = await get_health_context(session, user.id)
        if health_ctx:
            lines.append(health_ctx)
            lines.append("")
    except Exception:
        pass

    # ─── Financial Summary ─────────────────────────────────────────────────────
    try:
        from bot.core.finance import build_finance_context
        fin_ctx = await build_finance_context(session, user.id)
        if fin_ctx:
            lines.append(fin_ctx)
            lines.append("")
    except Exception:
        pass

    # ─── Pattern Insights ─────────────────────────────────────────────────────
    try:
        from bot.core.pattern_engine import get_pattern_summary
        pattern_ctx = await get_pattern_summary(session, user.id)
        if pattern_ctx:
            lines.append(pattern_ctx)
            lines.append("")
    except Exception:
        pass

    # ─── Relationship Context ─────────────────────────────────────────────────
    try:
        from bot.core.relationships import get_relationship_context
        rel_ctx = await get_relationship_context(session, user.id)
        if rel_ctx:
            lines.append(rel_ctx)
    except Exception:
        pass

    # ─── Pending Prompt State ─────────────────────────────────────────────────
    try:
        from bot.core.smart_detector import get_pending_prompt
        pending = get_pending_prompt(user.id)
        if pending:
            doc_map = {"journal": "Tagebuch", "gratitude": "Dankbarkeit"}
            doc = doc_map.get(pending, pending)
            lines.append(f"⚡ AKTIVER PROMPT: Nutzer wurde gerade für '{pending}' aufgefordert.")
            lines.append(f"  → Die nächste Texteingabe als {pending.upper()}-Eintrag behandeln.")
            lines.append(f"  → SOFORT store_document_entry(document='{doc}', content=...) aufrufen.")
            lines.append("")
    except Exception:
        pass

    # ─── User Settings ────────────────────────────────────────────────────────
    s = user.settings or {}
    prio = "AN" if s.get("priorities_enabled", True) else "AUS"
    review = "AN" if s.get("review_enabled", True) else "AUS"
    proactive = "AN" if s.get("proactive_enabled", True) else "AUS"
    lines.append(f"⚙️ Settings: Prioritäten={prio}, Review={review}, Proaktiv={proactive}")
    lines.append("")

    if len(lines) <= 2:
        return "Noch keine Daten. Der User ist neu — hilf ihm, sein erstes Ziel anzulegen."

    return "\n".join(lines)
