"""Phase 8.1: Smart Reflection — 7-question guided flow with AI summary."""
import json
import logging
from datetime import date, datetime, timedelta
from typing import Optional

from openai import AsyncOpenAI
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from bot.config import settings
from bot.database.models import (
    Log, Objective, Routine, RoutineCompletion, Task, User,
    WeeklyPriority, WeeklyReflection,
)

logger = logging.getLogger(__name__)
openai_client = AsyncOpenAI(api_key=settings.openai_api_key)

# ─── Questions ───────────────────────────────────────────────────────────────

_Q1 = (
    "1️⃣ *Was war dein größter Erfolg oder dein bester Moment diese Woche?*\n\n"
    "_(Was machst du nächste Woche wieder?)_"
)
_Q2 = (
    "2️⃣ *Wo bist du hinter deinen Erwartungen zurückgeblieben?*\n\n"
    "_(Was hält dich zurück — und was würdest du anders machen?)_"
)
_Q3 = (
    "3️⃣ *Wie bewertest du diese Woche insgesamt?*\n\n"
    "Tippe eine Zahl von *1–10*."
)
_Q4 = (
    "4️⃣ *Was war deine wichtigste Erkenntnis oder Lektion diese Woche?*"
)
_Q5 = (
    "5️⃣ *Was nimmst du dir als konkreten Vorsatz für nächste Woche vor?*\n\n"
    "_(Eine klare, umsetzbare Sache)_"
)
_Q6_TEMPLATE = (
    "6️⃣ *Welche deiner Objectives willst du nächste Woche priorisieren?*\n\n"
    "Aktive Ziele:\n{objectives_list}\n\n"
    "Tippe 1–3 Nummern (z.B. `1 3`)."
)
_Q7 = (
    "7️⃣ *Was sind deine 1–3 wichtigsten Ziele für die nächsten 4 Wochen?*\n\n"
    "Beschreib sie kurz in Freitext — ich erstelle daraus konkrete Objectives & Tasks."
)
_Q7_CONFIRM = (
    "Soll ich diese Ziele anlegen?\n\n"
    "Tippe *Ja* oder *Nein*."
)


# ─── Public API ──────────────────────────────────────────────────────────────

async def get_active_reflection(session: AsyncSession, user_id: int) -> Optional[WeeklyReflection]:
    """Return the in-progress reflection for a user, or None."""
    result = await session.execute(
        select(WeeklyReflection).where(and_(
            WeeklyReflection.user_id == user_id,
            WeeklyReflection.status == "in_progress",
        ))
    )
    return result.scalar_one_or_none()


async def start_reflection(session: AsyncSession, user_id: int) -> tuple[WeeklyReflection, str]:
    """Create a new weekly reflection record and return (record, Q1 text)."""
    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    week_number = today.isocalendar()[1]
    year = today.year

    reflection = WeeklyReflection(
        user_id=user_id,
        week_start=week_start,
        week_number=week_number,
        year=year,
        status="in_progress",
        current_question=1,
        raw_answers={},
    )
    session.add(reflection)
    await session.flush()
    return reflection, _Q1


async def handle_reflection_answer(
    session: AsyncSession,
    user: User,
    reflection: WeeklyReflection,
    text: str,
) -> str:
    """
    Process a user's answer for the current reflection question.
    Returns the next message to send (next question, confirmation, or summary).
    """
    q = reflection.current_question

    if q == 1:
        return await _handle_q1(session, reflection, text)
    elif q == 2:
        return await _handle_q2(session, reflection, text)
    elif q == 3:
        return await _handle_q3(session, reflection, text)
    elif q == 4:
        return await _handle_q4(session, reflection, text)
    elif q == 5:
        return await _handle_q5(session, reflection, text)
    elif q == 6:
        return await _handle_q6(session, user, reflection, text)
    elif q == 7:
        return await _handle_q7(session, reflection, text)
    elif q == 8:
        return await _handle_q7_confirm(session, user, reflection, text)
    else:
        return "✅ Deine Reflexion ist bereits abgeschlossen."


async def get_week_stats(session: AsyncSession, user_id: int) -> dict:
    """Get statistics for the current week."""
    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    week_start_dt = datetime.combine(week_start, datetime.min.time())
    week_end_dt = datetime.combine(today, datetime.max.time())

    done_result = await session.execute(
        select(Task).where(and_(
            Task.user_id == user_id,
            Task.status == "done",
            Task.completed_at >= week_start_dt,
            Task.completed_at <= week_end_dt,
            Task.category != "shopping",
        ))
    )
    done_tasks = done_result.scalars().all()

    workout_result = await session.execute(
        select(Log).where(and_(
            Log.user_id == user_id,
            Log.log_type == "workout",
            Log.logged_at >= week_start_dt,
            Log.logged_at <= week_end_dt,
        ))
    )
    workout_days = len({l.logged_at.date() for l in workout_result.scalars().all()})

    mood_result = await session.execute(
        select(Log).where(and_(
            Log.user_id == user_id,
            Log.log_type == "mood",
            Log.logged_at >= week_start_dt,
            Log.logged_at <= week_end_dt,
        ))
    )
    mood_logs = mood_result.scalars().all()
    mood_scores = [l.data.get("score") for l in mood_logs if l.data.get("score")]
    mood_avg = round(sum(mood_scores) / len(mood_scores), 1) if mood_scores else None

    routine_result = await session.execute(
        select(Routine).where(and_(Routine.user_id == user_id, Routine.status == "active"))
    )
    routines = routine_result.scalars().all()
    comp_result = await session.execute(
        select(RoutineCompletion).where(and_(
            RoutineCompletion.user_id == user_id,
            RoutineCompletion.completed_at >= week_start_dt,
            RoutineCompletion.completed_at <= week_end_dt,
        ))
    )
    completions = comp_result.scalars().all()
    max_completions = len(routines) * 7
    routine_rate = round(len(completions) / max_completions * 100) if max_completions > 0 else 0

    obj_result = await session.execute(
        select(Objective).where(and_(
            Objective.user_id == user_id,
            Objective.status == "active",
        ))
    )
    active_objectives = obj_result.scalars().all()

    return {
        "tasks_done": len(done_tasks),
        "workout_days": workout_days,
        "routine_rate": routine_rate,
        "mood_avg": mood_avg,
        "active_objectives": len(active_objectives),
        "done_task_titles": [t.title for t in done_tasks[:5]],
    }


# ─── Per-question handlers ────────────────────────────────────────────────────

async def _handle_q1(session: AsyncSession, r: WeeklyReflection, text: str) -> str:
    r.biggest_win = text
    r.current_question = 2
    _update_raw(r, "q1", text)
    await session.flush()
    return _Q2


async def _handle_q2(session: AsyncSession, r: WeeklyReflection, text: str) -> str:
    r.biggest_blocker = text
    r.current_question = 3
    _update_raw(r, "q2", text)
    await session.flush()
    return _Q3


async def _handle_q3(session: AsyncSession, r: WeeklyReflection, text: str) -> str:
    score = _parse_score(text)
    if score is None:
        return "Bitte tippe eine Zahl zwischen 1 und 10."
    r.week_score = score
    r.current_question = 4
    _update_raw(r, "q3", str(score))
    await session.flush()
    emoji = "🔥" if score >= 8 else "👍" if score >= 6 else "😐" if score >= 4 else "😔"
    return f"{emoji} Woche bewertet: *{score}/10*\n\n{_Q4}"


async def _handle_q4(session: AsyncSession, r: WeeklyReflection, text: str) -> str:
    r.key_learning = text
    r.current_question = 5
    _update_raw(r, "q4", text)
    await session.flush()
    return _Q5


async def _handle_q5(session: AsyncSession, r: WeeklyReflection, text: str) -> str:
    _update_raw(r, "q5", text)
    r.current_question = 6
    await session.flush()

    # Build objectives list for Q6
    obj_result = await session.execute(
        select(Objective)
        .options(selectinload(Objective.key_results))
        .where(and_(Objective.user_id == r.user_id, Objective.status == "active"))
        .order_by(Objective.created_at)
    )
    objectives = obj_result.scalars().all()

    if not objectives:
        # Skip Q6 if no active objectives
        _update_raw(r, "q6_skipped", "no_objectives")
        r.current_question = 7
        await session.flush()
        return _Q7

    lines = []
    obj_map = {}
    for i, obj in enumerate(objectives, 1):
        kr_count = len([kr for kr in obj.key_results if kr.status == "active"])
        line = f"  *{i}.* {obj.title} [{obj.category}]"
        if kr_count:
            line += f" — {kr_count} KR"
        lines.append(line)
        obj_map[str(i)] = obj.id

    _update_raw(r, "q6_obj_map", obj_map)
    await session.flush()

    objectives_list = "\n".join(lines)
    return _Q6_TEMPLATE.format(objectives_list=objectives_list)


async def _handle_q6(
    session: AsyncSession, user: User, r: WeeklyReflection, text: str
) -> str:
    raw = r.raw_answers or {}
    obj_map: dict = raw.get("q6_obj_map", {})

    # Parse numbers from user input
    selected_nums = [s.strip() for s in text.replace(",", " ").split() if s.strip().isdigit()]
    selected_ids = []
    for num in selected_nums[:3]:
        obj_id = obj_map.get(num)
        if obj_id:
            selected_ids.append(obj_id)

    if selected_ids:
        # Fetch objectives to get titles
        obj_result = await session.execute(
            select(Objective).where(
                and_(Objective.id.in_(selected_ids), Objective.user_id == r.user_id)
            )
        )
        objectives = {o.id: o for o in obj_result.scalars().all()}

        week_start = r.week_start
        # Delete existing priorities for this week (if any)
        existing_result = await session.execute(
            select(WeeklyPriority).where(and_(
                WeeklyPriority.user_id == r.user_id,
                WeeklyPriority.week_start == week_start,
            ))
        )
        for existing in existing_result.scalars().all():
            await session.delete(existing)

        priority_lines = []
        for rank, obj_id in enumerate(selected_ids, 1):
            obj = objectives.get(obj_id)
            if obj:
                wp = WeeklyPriority(
                    user_id=r.user_id,
                    week_start=week_start,
                    priority_rank=rank,
                    title=obj.title,
                    linked_objective_id=obj_id,
                    status="active",
                )
                session.add(wp)
                priority_lines.append(f"  {rank}. {obj.title}")

        await session.flush()
        _update_raw(r, "q6", text)
        _update_raw(r, "q6_selected_ids", selected_ids)
        confirm = "✅ Prioritäten gesetzt:\n" + "\n".join(priority_lines) + "\n\n"
    else:
        confirm = "_(Keine Prioritäten gesetzt)_\n\n"
        _update_raw(r, "q6", "skipped")

    r.current_question = 7
    await session.flush()
    return confirm + _Q7


async def _handle_q7(session: AsyncSession, r: WeeklyReflection, text: str) -> str:
    """User described their 4-week goals. Generate AI proposal."""
    _update_raw(r, "q7_input", text)

    try:
        proposal = await _generate_goal_proposal(text)
    except Exception as e:
        logger.warning("Goal proposal generation failed: %s", e)
        r.current_question = 9
        await _complete_reflection(session, r)
        return await _build_final_summary(session, r)

    _update_raw(r, "q7_proposal", proposal)
    r.current_question = 8
    await session.flush()

    # Format proposal for display
    lines = ["🎯 *Vorgeschlagene Ziele & Tasks für die nächsten 4 Wochen:*\n"]
    for i, goal in enumerate(proposal.get("goals", []), 1):
        lines.append(f"*{i}. {goal['title']}* [{goal.get('category', 'personal')}]")
        if goal.get("description"):
            lines.append(f"   _{goal['description']}_")
        for task in goal.get("tasks", [])[:3]:
            lines.append(f"   ☐ {task}")
        lines.append("")

    lines.append(_Q7_CONFIRM)
    return "\n".join(lines)


async def _handle_q7_confirm(
    session: AsyncSession, user: User, r: WeeklyReflection, text: str
) -> str:
    """User confirms or rejects the AI goal proposal."""
    answer = text.strip().lower()
    raw = r.raw_answers or {}
    proposal = raw.get("q7_proposal", {})
    created_lines = []

    if answer in ("ja", "yes", "j", "y", "✅", "👍"):
        from bot.core.objectives import create_objective, suggest_tasks_for_objective
        for goal in proposal.get("goals", []):
            try:
                obj = await create_objective(
                    session,
                    user.id,
                    title=goal["title"],
                    category=goal.get("category", "personal"),
                    description=goal.get("description"),
                )
                tasks = [{"title": t, "priority": 3} for t in goal.get("tasks", [])]
                if tasks:
                    await suggest_tasks_for_objective(session, user.id, obj.id, tasks)
                created_lines.append(f"✅ {goal['title']}")
            except Exception as e:
                logger.warning("Failed to create goal %s: %s", goal.get("title"), e)

        _update_raw(r, "q7_confirmed", True)
        if created_lines:
            confirm_text = "✅ Ziele angelegt:\n" + "\n".join(created_lines) + "\n\n"
        else:
            confirm_text = "_(Ziele konnten nicht angelegt werden)_\n\n"
    else:
        _update_raw(r, "q7_confirmed", False)
        confirm_text = "_(Ziele nicht angelegt)_\n\n"

    r.current_question = 9
    await _complete_reflection(session, r)
    summary = await _build_final_summary(session, r)
    return confirm_text + summary


# ─── Completion & AI Summary ─────────────────────────────────────────────────

async def _complete_reflection(session: AsyncSession, r: WeeklyReflection) -> None:
    """Mark reflection complete and generate AI summary."""
    r.status = "completed"
    try:
        ai_summary = await _generate_ai_summary(session, r)
        r.ai_summary = ai_summary
    except Exception as e:
        logger.warning("AI summary generation failed: %s", e)
        r.ai_summary = {}
    await session.flush()


async def _build_final_summary(session: AsyncSession, r: WeeklyReflection) -> str:
    """Build the formatted final message with AI summary."""
    ai = r.ai_summary or {}
    week_str = f"KW{r.week_number}/{r.year}"

    lines = [f"🪞 *Reflexion {week_str} abgeschlossen!*"]
    if r.week_score:
        score_bar = "⭐" * r.week_score + "☆" * (10 - r.week_score)
        lines.append(f"Dein Wochen-Score: {score_bar} *{r.week_score}/10*")
    lines.append("")

    recommendations = ai.get("recommendations", [])
    if recommendations:
        lines.append("💡 *Top 3 Empfehlungen für nächste Woche:*")
        for i, rec in enumerate(recommendations[:3], 1):
            lines.append(f"  {i}. {rec}")
        lines.append("")

    adjustments = ai.get("goal_adjustments", [])
    if adjustments:
        lines.append("🎯 *Vorgeschlagene Ziel-Anpassungen:*")
        for adj in adjustments[:3]:
            lines.append(f"  • {adj}")
        lines.append("")

    motivation = ai.get("motivation", "")
    if motivation:
        lines.append(f"🔥 _{motivation}_")

    return "\n".join(lines)


async def _generate_ai_summary(session: AsyncSession, r: WeeklyReflection) -> dict:
    """Call GPT-4o to generate recommendations, adjustments, and motivation."""
    stats = await get_week_stats(session, r.user_id)
    raw = r.raw_answers or {}

    week_str = f"KW{r.week_number}/{r.year}"
    context = f"""WOCHEN-REFLEXION {week_str}

WOCHENDATEN:
- Tasks erledigt: {stats['tasks_done']}
- Workout-Tage: {stats['workout_days']}
- Routinen-Rate: {stats['routine_rate']}%
- Stimmung Ø: {stats['mood_avg'] or 'n/a'}/10
- Aktive Ziele: {stats['active_objectives']}

ANTWORTEN:
1. Größter Erfolg: {r.biggest_win or 'keine Angabe'}
2. Größter Blocker: {r.biggest_blocker or 'keine Angabe'}
3. Wochen-Score: {r.week_score or 'keine Angabe'}/10
4. Wichtigste Erkenntnis: {r.key_learning or 'keine Angabe'}
5. Vorsatz nächste Woche: {raw.get('q5', 'keine Angabe')}
6. Priorisierte Objectives: {len(raw.get('q6_selected_ids', []))} ausgewählt
7. 4-Wochen-Ziele: {raw.get('q7_input', 'keine Angabe')}"""

    prompt = f"""{context}

Du bist ein persönlicher COO. Analysiere diese Wochen-Reflexion und antworte NUR mit validem JSON:

{{
  "recommendations": ["<konkrete Handlungsempfehlung 1>", "<2>", "<3>"],
  "goal_adjustments": ["<Ziel das pausiert/angepasst werden sollte + warum>"],
  "motivation": "<persönliche Motivationsnachricht, 2-3 Sätze, Du-Form>"
}}

Sei konkret, direkt und motivierend. Keine Floskeln."""

    response = await openai_client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=600,
        temperature=0.7,
        response_format={"type": "json_object"},
    )
    raw_json = response.choices[0].message.content or "{}"
    try:
        return json.loads(raw_json)
    except Exception:
        return {"recommendations": [], "goal_adjustments": [], "motivation": raw_json}


async def _generate_goal_proposal(user_goals_text: str) -> dict:
    """Call GPT-4o to turn free-text goals into structured Objective proposals."""
    prompt = f"""Der Nutzer hat folgende Ziele für die nächsten 4 Wochen beschrieben:

"{user_goals_text}"

Erstelle daraus strukturierte Objectives mit konkreten Tasks. Antworte NUR mit validem JSON:

{{
  "goals": [
    {{
      "title": "<kurzer Objective-Titel>",
      "category": "<health|business|personal|fitness|finance|learning>",
      "description": "<kurze Beschreibung, optional>",
      "tasks": ["<Task 1>", "<Task 2>", "<Task 3>"]
    }}
  ]
}}

Maximal 3 Goals. Tasks sollen konkret und umsetzbar sein (Verben, messbar)."""

    response = await openai_client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=600,
        temperature=0.5,
        response_format={"type": "json_object"},
    )
    raw_json = response.choices[0].message.content or "{}"
    return json.loads(raw_json)


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _update_raw(r: WeeklyReflection, key: str, value) -> None:
    """Safely update raw_answers dict (handles SQLAlchemy JSON mutation)."""
    current = dict(r.raw_answers or {})
    current[key] = value
    r.raw_answers = current


def _parse_score(text: str) -> Optional[int]:
    """Parse a 1-10 score from user input."""
    text = text.strip().rstrip(".")
    try:
        val = int(text)
        if 1 <= val <= 10:
            return val
    except ValueError:
        pass
    return None
