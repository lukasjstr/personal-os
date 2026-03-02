"""Phase 4: Evening review generation and sending via GPT-4o."""
import logging
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from openai import AsyncOpenAI
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import settings
from bot.database.connection import get_session
from bot.database.models import (
    DailyBrief, Log, Routine, RoutineCompletion, Task, User,
)
from bot.telegram.sender import send_message

logger = logging.getLogger(__name__)
openai_client = AsyncOpenAI(api_key=settings.openai_api_key)


async def send_evening_review() -> None:
    """Check all active users and send evening review if their configured time matches now."""
    now_berlin = datetime.now(tz=ZoneInfo("Europe/Berlin"))
    current_time = now_berlin.strftime("%H:%M")
    today = now_berlin.date()

    async with get_session() as session:
        result = await session.execute(
            select(User).where(User.is_active == True)  # noqa: E712
        )
        users = result.scalars().all()

        for user in users:
            s = user.settings or {}
            if not s.get("review_enabled", True):
                continue

            review_time = s.get("evening_review_time", "21:00")
            if current_time != review_time:
                continue

            brief = await _get_or_create_daily_brief(session, user.id, today)
            if brief.review_sent_at:
                continue

            try:
                text = await _generate_review_for_user(session, user, today)
                success = await send_message(user.telegram_id, text)
                if success:
                    brief.review_sent_at = datetime.utcnow()
                    await session.flush()
                    logger.info("Evening review sent to user %s", user.id)
            except Exception:
                logger.exception("Failed to send evening review to user %s", user.id)


async def _generate_review_for_user(session: AsyncSession, user: User, today: date) -> str:
    """Generate personalized evening review using GPT-4o."""
    today_start = datetime.combine(today, datetime.min.time())

    done_result = await session.execute(
        select(Task).where(and_(
            Task.user_id == user.id,
            Task.status == "done",
            Task.completed_at >= today_start,
            Task.category != "shopping",
        ))
    )
    done_tasks = done_result.scalars().all()

    open_result = await session.execute(
        select(Task).where(and_(
            Task.user_id == user.id,
            Task.status.in_(["todo", "in_progress"]),
            Task.category != "shopping",
        )).order_by(Task.priority.asc()).limit(3)
    )
    open_tasks = open_result.scalars().all()

    routine_result = await session.execute(
        select(Routine).where(and_(Routine.user_id == user.id, Routine.status == "active"))
    )
    routines = routine_result.scalars().all()

    comp_result = await session.execute(
        select(RoutineCompletion.routine_id).where(and_(
            RoutineCompletion.user_id == user.id,
            RoutineCompletion.completed_at >= today_start,
        ))
    )
    done_routine_ids = set(comp_result.scalars().all())

    water_result = await session.execute(
        select(Log).where(and_(
            Log.user_id == user.id,
            Log.log_type == "water",
            Log.logged_at >= today_start,
        ))
    )
    water_total = sum(l.data.get("amount", 0) for l in water_result.scalars().all())

    workout_result = await session.execute(
        select(Log).where(and_(
            Log.user_id == user.id,
            Log.log_type == "workout",
            Log.logged_at >= today_start,
        ))
    )
    workouts_today = workout_result.scalars().all()

    week_start = datetime.combine(today - timedelta(days=6), datetime.min.time())
    mood_result = await session.execute(
        select(Log).where(and_(
            Log.user_id == user.id,
            Log.log_type == "mood",
            Log.logged_at >= week_start,
        )).order_by(Log.logged_at.asc())
    )
    mood_logs = mood_result.scalars().all()
    mood_scores = [l.data.get("score") for l in mood_logs if l.data.get("score")]
    mood_avg = round(sum(mood_scores) / len(mood_scores), 1) if mood_scores else None

    context_lines = []

    if done_tasks:
        context_lines.append(f"ERLEDIGTE TASKS HEUTE ({len(done_tasks)}):")
        for t in done_tasks[:5]:
            context_lines.append(f"  ✅ {t.title}")
    else:
        context_lines.append("ERLEDIGTE TASKS HEUTE: keine")

    if routines:
        done_count = len([r for r in routines if r.id in done_routine_ids])
        context_lines.append(f"\nROUTINEN: {done_count}/{len(routines)} erledigt")
        for r in routines:
            status = "✅" if r.id in done_routine_ids else "⚠️"
            context_lines.append(f"  {status} {r.title}")

    context_lines.append(f"\nWASSER HEUTE: {water_total:.1f}L")

    if workouts_today:
        exercises = [l.data.get("exercise", "Training") for l in workouts_today[:3]]
        context_lines.append(f"WORKOUT: {', '.join(exercises)}")

    if mood_avg:
        context_lines.append(f"MOOD SCHNITT DIESE WOCHE: {mood_avg}/10")

    if open_tasks:
        context_lines.append("\nNOCH OFFEN (Top 3 für morgen):")
        for t in open_tasks:
            context_lines.append(f"  P{t.priority}: {t.title}")

    name = user.first_name or "Chef"
    day_map = {
        "Monday": "Montag", "Tuesday": "Dienstag", "Wednesday": "Mittwoch",
        "Thursday": "Donnerstag", "Friday": "Freitag", "Saturday": "Samstag", "Sunday": "Sonntag",
    }
    day_name = day_map.get(today.strftime("%A"), today.strftime("%A"))
    context = "\n".join(context_lines)

    prompt = f"""Du bist der persönliche COO von {name}. Heute ist {day_name}, {today.strftime('%d.%m.%Y')}.

TAGES-DATEN:
{context}

Erstelle einen persönlichen Tages-Review auf Deutsch. Format:
- Kurze Einleitung (1 Satz)
- ✅ Was heute gut lief (erledigte Tasks, Routinen, Workout)
- ⚠️ Was offen blieb (nicht erledigte Routinen oder Tasks)
- 💧 Wasser-Stand mit Kommentar (gut/zu wenig)
- 📋 Top Prioritäten für morgen (aus offenen Tasks)
- Abschluss: stelle genau diese Frage: "Wie war dein Tag? Sag mir eine Zahl von 1-10."

Sei ehrlich, unterstützend und prägnant. Max 250 Wörter."""

    try:
        response = await openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500,
            temperature=0.7,
        )
        return response.choices[0].message.content or _fallback_review(
            done_tasks, routines, done_routine_ids, water_total, name
        )
    except Exception:
        logger.exception("GPT-4o failed for evening review, using fallback")
        return _fallback_review(done_tasks, routines, done_routine_ids, water_total, name)


def _fallback_review(
    done_tasks: list, routines: list, done_routine_ids: set, water_total: float, name: str
) -> str:
    lines = [f"🌙 Tages-Review — {name}\n"]
    if done_tasks:
        lines.append("✅ ERLEDIGT:")
        for t in done_tasks[:3]:
            lines.append(f"  ✅ {t.title}")
        lines.append("")
    if routines:
        done_count = len([r for r in routines if r.id in done_routine_ids])
        lines.append(f"🔄 Routinen: {done_count}/{len(routines)}")
    lines.append(f"💧 Wasser: {water_total:.1f}L")
    lines.append("\nWie war dein Tag? Sag mir eine Zahl von 1-10.")
    return "\n".join(lines)


async def _get_or_create_daily_brief(
    session: AsyncSession, user_id: int, brief_date: date
) -> DailyBrief:
    result = await session.execute(
        select(DailyBrief).where(and_(
            DailyBrief.user_id == user_id,
            DailyBrief.brief_date == brief_date,
        ))
    )
    brief = result.scalar_one_or_none()
    if not brief:
        brief = DailyBrief(user_id=user_id, brief_date=brief_date)
        session.add(brief)
        await session.flush()
    return brief
