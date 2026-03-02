"""Phase 4: Morning brief generation and sending via GPT-4o."""
import logging
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from openai import AsyncOpenAI
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import settings
from bot.database.connection import get_session
from bot.database.models import (
    CalendarEvent, DailyBrief, Log, Routine, Task, User,
)
from bot.telegram.sender import send_message

logger = logging.getLogger(__name__)
openai_client = AsyncOpenAI(api_key=settings.openai_api_key)


async def send_morning_brief() -> None:
    """Check all active users and send morning brief if their configured time matches now."""
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
            if not s.get("priorities_enabled", True):
                continue

            brief_time = s.get("morning_brief_time", "06:30")
            if current_time != brief_time:
                continue

            brief = await _get_or_create_daily_brief(session, user.id, today)
            if brief.brief_sent_at:
                continue

            try:
                text = await _generate_brief_for_user(session, user, today)
                success = await send_message(user.telegram_id, text)
                if success:
                    brief.brief_sent_at = datetime.utcnow()
                    await session.flush()
                    logger.info("Morning brief sent to user %s", user.id)
            except Exception:
                logger.exception("Failed to send morning brief to user %s", user.id)


async def _generate_brief_for_user(session: AsyncSession, user: User, today: date) -> str:
    """Generate personalized morning brief using GPT-4o."""
    today_start = datetime.combine(today, datetime.min.time())
    today_end = datetime.combine(today, datetime.max.time())

    task_result = await session.execute(
        select(Task).where(and_(
            Task.user_id == user.id,
            Task.status.in_(["todo", "in_progress"]),
            Task.category != "shopping",
        )).order_by(Task.priority.asc(), Task.due_date.asc().nulls_last()).limit(5)
    )
    tasks = task_result.scalars().all()

    routine_result = await session.execute(
        select(Routine).where(and_(
            Routine.user_id == user.id,
            Routine.status == "active",
            Routine.time_of_day.in_(["morning", "anytime"]),
        )).order_by(Routine.sort_order.asc(), Routine.id.asc())
    )
    routines = routine_result.scalars().all()

    cal_result = await session.execute(
        select(CalendarEvent).where(and_(
            CalendarEvent.user_id == user.id,
            CalendarEvent.start_time >= today_start,
            CalendarEvent.start_time <= today_end,
        )).order_by(CalendarEvent.start_time)
    )
    events = cal_result.scalars().all()

    overdue_result = await session.execute(
        select(Task).where(and_(
            Task.user_id == user.id,
            Task.status.in_(["todo", "in_progress"]),
            Task.due_date < today,
            Task.category != "shopping",
        ))
    )
    overdue = overdue_result.scalars().all()

    yesterday_start = datetime.combine(today - timedelta(days=1), datetime.min.time())
    mood_result = await session.execute(
        select(Log).where(and_(
            Log.user_id == user.id,
            Log.log_type == "mood",
            Log.logged_at >= yesterday_start,
            Log.logged_at < today_start,
        )).order_by(Log.logged_at.desc()).limit(1)
    )
    yesterday_mood = mood_result.scalar_one_or_none()

    context_lines = []

    if tasks:
        context_lines.append("OFFENE TASKS (nach Priorität):")
        for t in tasks:
            due = f" [fällig: {t.due_date}]" if t.due_date else ""
            overdue_flag = " ⚠️ ÜBERFÄLLIG" if t.due_date and t.due_date < today else ""
            context_lines.append(f"  P{t.priority}: {t.title}{due}{overdue_flag}")

    if routines:
        context_lines.append("\nMORGEN-ROUTINEN:")
        for r in routines:
            context_lines.append(f"  ☐ {r.title}")

    if events:
        context_lines.append("\nTERMINE HEUTE:")
        for e in events:
            time_str = e.start_time.strftime("%H:%M") if not e.all_day else "ganztägig"
            context_lines.append(f"  {time_str}: {e.title}")

    if overdue:
        context_lines.append(f"\nÜBERFÄLLIGE TASKS: {len(overdue)}")
        for t in overdue[:3]:
            context_lines.append(f"  ⚠️ {t.title} (fällig: {t.due_date})")

    if yesterday_mood:
        context_lines.append(f"\nGESTRIGE STIMMUNG: {yesterday_mood.data.get('score', '?')}/10")

    name = user.first_name or "Chef"
    day_map = {
        "Monday": "Montag", "Tuesday": "Dienstag", "Wednesday": "Mittwoch",
        "Thursday": "Donnerstag", "Friday": "Freitag", "Saturday": "Samstag", "Sunday": "Sonntag",
    }
    day_name = day_map.get(today.strftime("%A"), today.strftime("%A"))
    date_str = today.strftime("%d.%m.%Y")
    context = "\n".join(context_lines) if context_lines else "Noch keine Daten vorhanden."

    prompt = f"""Du bist der persönliche COO von {name}. Heute ist {day_name}, {date_str}.

VERFÜGBARE DATEN:
{context}

Erstelle einen prägnanten Morning Brief auf Deutsch. Format:
- Kurze Begrüßung (1 Satz)
- 🎯 TOP 3 PRIORITÄTEN (wähle die 3 wichtigsten Tasks)
- 📋 ROUTINEN HEUTE (alle auflisten mit ☐)
- 📅 KALENDER (nur wenn Events vorhanden)
- 💡 REMINDER (nur wenn überfällige Tasks oder wichtige Hinweise vorhanden)
- Kurzer motivierender Abschluss-Satz

Sei direkt und prägnant. Max 300 Wörter."""

    try:
        response = await openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=600,
            temperature=0.7,
        )
        return response.choices[0].message.content or _fallback_brief(tasks, routines, events, name)
    except Exception:
        logger.exception("GPT-4o failed for morning brief, using fallback")
        return _fallback_brief(tasks, routines, events, name)


def _fallback_brief(tasks: list, routines: list, events: list, name: str) -> str:
    lines = [f"☀️ Guten Morgen, {name}!\n"]
    if tasks:
        lines.append("🎯 TOP PRIORITÄTEN")
        for t in tasks[:3]:
            lines.append(f"  {t.priority}. {t.title}")
        lines.append("")
    if routines:
        lines.append("📋 ROUTINEN HEUTE")
        for r in routines:
            lines.append(f"  ☐ {r.title}")
        lines.append("")
    if events:
        lines.append("📅 KALENDER")
        for e in events:
            time_str = e.start_time.strftime("%H:%M") if not e.all_day else "ganztägig"
            lines.append(f"  {time_str}: {e.title}")
        lines.append("")
    lines.append("Los geht's! 💪")
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
