"""Phase 4: Weekly reflection — sends AI-generated summary every Sunday."""
import logging
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from openai import AsyncOpenAI
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import settings
from bot.database.connection import get_session
from bot.database.models import (
    Log, Objective, Routine, RoutineCompletion, Task, User, WeeklyReflection,
)
from bot.telegram.sender import send_message

logger = logging.getLogger(__name__)
openai_client = AsyncOpenAI(api_key=settings.openai_api_key)


async def check_and_trigger_reflections() -> None:
    """
    Runs every minute. On Sundays, checks each user's reflection time.
    Sends a GPT-4o-generated weekly summary with reflection questions.
    """
    now_berlin = datetime.now(tz=ZoneInfo("Europe/Berlin"))
    today = now_berlin.date()

    # Only run on Sundays
    if today.weekday() != 6:
        return

    current_time = now_berlin.strftime("%H:%M")

    async with get_session() as session:
        result = await session.execute(
            select(User).where(User.is_active == True)  # noqa: E712
        )
        users = result.scalars().all()

        for user in users:
            s = user.settings or {}
            if not s.get("reflection_enabled", True):
                continue

            reflection_time = s.get("weekly_reflection_time", "19:00")
            if current_time != reflection_time:
                continue

            # Calculate week start (last Monday)
            week_start = today - timedelta(days=today.weekday())
            week_number = today.isocalendar()[1]
            year = today.year

            # Check if already sent this week
            existing = await session.execute(
                select(WeeklyReflection).where(and_(
                    WeeklyReflection.user_id == user.id,
                    WeeklyReflection.week_start == week_start,
                ))
            )
            if existing.scalar_one_or_none():
                continue

            try:
                text = await _generate_weekly_reflection(session, user, week_start, today)
                success = await send_message(user.telegram_id, text)
                if success:
                    reflection = WeeklyReflection(
                        user_id=user.id,
                        week_start=week_start,
                        week_number=week_number,
                        year=year,
                        status="in_progress",
                    )
                    session.add(reflection)
                    await session.flush()
                    logger.info("Weekly reflection sent to user %s", user.id)
            except Exception:
                logger.exception("Failed to send weekly reflection to user %s", user.id)


async def _generate_weekly_reflection(
    session: AsyncSession, user: User, week_start: date, week_end: date
) -> str:
    """Generate a weekly reflection summary using GPT-4o."""
    week_start_dt = datetime.combine(week_start, datetime.min.time())
    week_end_dt = datetime.combine(week_end, datetime.max.time())

    # Tasks completed this week
    done_result = await session.execute(
        select(Task).where(and_(
            Task.user_id == user.id,
            Task.status == "done",
            Task.completed_at >= week_start_dt,
            Task.completed_at <= week_end_dt,
            Task.category != "shopping",
        ))
    )
    done_tasks = done_result.scalars().all()

    # Workouts this week
    workout_result = await session.execute(
        select(Log).where(and_(
            Log.user_id == user.id,
            Log.log_type == "workout",
            Log.logged_at >= week_start_dt,
            Log.logged_at <= week_end_dt,
        ))
    )
    workout_days = len({l.logged_at.date() for l in workout_result.scalars().all()})

    # Mood this week
    mood_result = await session.execute(
        select(Log).where(and_(
            Log.user_id == user.id,
            Log.log_type == "mood",
            Log.logged_at >= week_start_dt,
            Log.logged_at <= week_end_dt,
        )).order_by(Log.logged_at.asc())
    )
    mood_logs = mood_result.scalars().all()
    mood_scores = [l.data.get("score") for l in mood_logs if l.data.get("score")]
    mood_avg = round(sum(mood_scores) / len(mood_scores), 1) if mood_scores else None

    # Routines completion rate this week
    routine_result = await session.execute(
        select(Routine).where(and_(Routine.user_id == user.id, Routine.status == "active"))
    )
    routines = routine_result.scalars().all()

    comp_result = await session.execute(
        select(RoutineCompletion).where(and_(
            RoutineCompletion.user_id == user.id,
            RoutineCompletion.completed_at >= week_start_dt,
            RoutineCompletion.completed_at <= week_end_dt,
        ))
    )
    completions = comp_result.scalars().all()
    days_in_week = 7
    max_completions = len(routines) * days_in_week
    routine_rate = round(len(completions) / max_completions * 100) if max_completions > 0 else 0

    # Active objectives progress
    obj_result = await session.execute(
        select(Objective).where(and_(
            Objective.user_id == user.id,
            Objective.status == "active",
        ))
    )
    active_objectives = obj_result.scalars().all()

    # Build context
    week_str = f"KW{week_start.isocalendar()[1]} ({week_start.strftime('%d.%m.')} – {week_end.strftime('%d.%m.%Y')})"
    context_lines = [
        f"WOCHE: {week_str}",
        f"TASKS ERLEDIGT: {len(done_tasks)}",
        f"WORKOUT-TAGE: {workout_days}",
        f"ROUTINEN-ERFÜLLUNGSRATE: {routine_rate}%",
    ]
    if mood_avg:
        context_lines.append(f"DURCHSCHNITTLICHE STIMMUNG: {mood_avg}/10")
    if active_objectives:
        context_lines.append(f"AKTIVE ZIELE: {len(active_objectives)}")
    if done_tasks:
        context_lines.append("\nERLEDIGTE TASKS DIESE WOCHE:")
        for t in done_tasks[:5]:
            context_lines.append(f"  ✅ {t.title}")
        if len(done_tasks) > 5:
            context_lines.append(f"  ... und {len(done_tasks) - 5} weitere")

    name = user.first_name or "Chef"
    context = "\n".join(context_lines)

    prompt = f"""Du bist der persönliche COO von {name}. Es ist Sonntag Abend — Zeit für die Wochen-Reflexion.

WOCHENDATEN:
{context}

Erstelle eine persönliche, reflektierende Wochen-Zusammenfassung auf Deutsch. Format:
- Kurze Begrüßung und Wochenüberblick (2-3 Sätze)
- 📊 WOCHENSTATISTIK (Tasks, Workouts, Routinen, Mood)
- 💪 Was diese Woche gut lief (basierend auf den Daten)
- Stelle genau diese 2 Fragen:
  "1. Was lief besonders gut diese Woche? Was machst du wieder?"
  "2. Was möchtest du nächste Woche besser machen?"

Sei persönlich, motivierend und ehrlich. Max 300 Wörter."""

    try:
        response = await openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=600,
            temperature=0.8,
        )
        return response.choices[0].message.content or _fallback_reflection(
            done_tasks, workout_days, routine_rate, mood_avg, name, week_str
        )
    except Exception:
        logger.exception("GPT-4o failed for weekly reflection, using fallback")
        return _fallback_reflection(done_tasks, workout_days, routine_rate, mood_avg, name, week_str)


def _fallback_reflection(
    done_tasks: list, workout_days: int, routine_rate: int,
    mood_avg: float | None, name: str, week_str: str
) -> str:
    lines = [
        f"🔮 Wochen-Reflexion — {week_str}\n",
        f"Hey {name}, hier ist deine Wochenzusammenfassung:\n",
        "📊 WOCHENSTATISTIK",
        f"  ✅ Tasks erledigt: {len(done_tasks)}",
        f"  💪 Workout-Tage: {workout_days}",
        f"  🔄 Routinen: {routine_rate}%",
    ]
    if mood_avg:
        lines.append(f"  😊 Stimmung Ø: {mood_avg}/10")
    lines.extend([
        "",
        "Bitte beantworte mir:",
        "1. Was lief besonders gut diese Woche? Was machst du wieder?",
        "2. Was möchtest du nächste Woche besser machen?",
    ])
    return "\n".join(lines)


async def send_reflection_invitation(user_id: int) -> None:
    """Kept for compatibility. The main logic is now in check_and_trigger_reflections."""
    logger.info("send_reflection_invitation called for user %s", user_id)
