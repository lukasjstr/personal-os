"""Day Scheduler — generates a time-blocked day plan and writes CalendarEvent rows.

Called daily at 06:00 (before morning brief). Produces:
- A complete hour-by-hour schedule for today
- CalendarEvent rows (event_type="work_block") linked to tasks/routines
- A "daily_focus" summary sentence

The morning brief reads these events to show the structured day plan.
"""
import json
import logging
from datetime import date, datetime, time, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

_BERLIN = ZoneInfo("Europe/Berlin")
_UTC = ZoneInfo("UTC")


def _berlin_to_utc(dt: datetime) -> datetime:
    """Convert naive Berlin-local datetime to naive UTC for DB storage."""
    if dt.tzinfo is not None:
        return dt.astimezone(_UTC).replace(tzinfo=None)
    return dt.replace(tzinfo=_BERLIN).astimezone(_UTC).replace(tzinfo=None)

from openai import AsyncOpenAI
from sqlalchemy import and_, delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from bot.config import settings
from bot.database.models import CalendarEvent, Routine, Task, User

logger = logging.getLogger(__name__)
_openai = AsyncOpenAI(api_key=settings.openai_api_key)

DAY_NAMES_DE = {
    "Monday": "Montag", "Tuesday": "Dienstag", "Wednesday": "Mittwoch",
    "Thursday": "Donnerstag", "Friday": "Freitag", "Saturday": "Samstag", "Sunday": "Sonntag",
}


async def generate_day_schedule(
    session: AsyncSession,
    user: User,
    target_date: Optional[date] = None,
) -> tuple[list[dict], str]:
    """Generate time-blocked schedule for target_date, write to CalendarEvent.

    Returns (full_schedule_list, daily_focus_string).
    full_schedule_list includes meals/breaks (not written to DB) for display.
    """
    if target_date is None:
        target_date = date.today()

    day_start = datetime.combine(target_date, time(0, 0))
    day_end = datetime.combine(target_date, time(23, 59))

    # Remove previously auto-scheduled work_block events for this day
    await session.execute(
        delete(CalendarEvent).where(and_(
            CalendarEvent.user_id == user.id,
            CalendarEvent.start_time >= day_start,
            CalendarEvent.start_time <= day_end,
            CalendarEvent.event_type == "work_block",
        ))
    )
    await session.flush()

    # Load open tasks for today (due today, overdue, or no due date)
    task_res = await session.execute(
        select(Task)
        .options(selectinload(Task.objective))
        .where(and_(
            Task.user_id == user.id,
            Task.status.in_(["todo", "in_progress"]),
            Task.category != "shopping",
            or_(
                Task.due_date <= target_date,
                Task.due_date.is_(None),
            ),
        ))
        .order_by(Task.priority.asc(), Task.due_date.asc().nulls_last())
        .limit(10)
    )
    tasks = task_res.scalars().all()

    # Load active routines
    routine_res = await session.execute(
        select(Routine).where(and_(
            Routine.user_id == user.id,
            Routine.status == "active",
        ))
    )
    routines = routine_res.scalars().all()

    # Load existing booked calendar events (non-work_block) to avoid conflicts
    existing_res = await session.execute(
        select(CalendarEvent).where(and_(
            CalendarEvent.user_id == user.id,
            CalendarEvent.start_time >= day_start,
            CalendarEvent.start_time <= day_end,
            CalendarEvent.event_type != "work_block",
        )).order_by(CalendarEvent.start_time)
    )
    existing_events = existing_res.scalars().all()

    # Build context
    tasks_text = "\n".join(
        f"  - ID={t.id} P{t.priority}: {t.title}"
        + (f" [Ziel: {t.objective.title[:40]}]" if t.objective else "")
        + (f" [fällig: {t.due_date}]" if t.due_date else "")
        for t in tasks
    ) or "  Keine offenen Tasks"

    routines_text = "\n".join(
        f"  - ID={r.id} ({r.time_of_day}): {r.title}"
        for r in routines
    ) or "  Keine Routinen"

    booked_text = "\n".join(
        f"  - {e.start_time.strftime('%H:%M')}"
        + (f"–{e.end_time.strftime('%H:%M')}" if e.end_time else "")
        + f": {e.title} [BELEGT]"
        for e in existing_events
    ) or "  Keine gebuchten Termine"

    user_settings = user.settings or {}
    wakeup = user_settings.get("wakeup_time", "06:30")
    sleep_time = user_settings.get("sleep_time", "22:30")
    day_name = DAY_NAMES_DE.get(target_date.strftime("%A"), target_date.strftime("%A"))
    date_str = target_date.strftime("%d.%m.%Y")

    prompt = f"""Erstelle einen vollständigen Tagesplan (Zeitblöcke) für {day_name}, {date_str}.
Aufwachzeit: {wakeup} | Schlafenszeit: {sleep_time}

Offene Tasks (nach Priorität einplanen):
{tasks_text}

Aktive Routinen:
{routines_text}

Bereits gebuchte Termine (NICHT überschreiben):
{booked_text}

Antworte NUR mit JSON:
{{
  "schedule": [
    {{"time": "07:00", "duration_minutes": 20, "title": "Frühstück", "type": "meal", "ref_id": null}},
    {{"time": "07:20", "duration_minutes": 15, "title": "<routine title>", "type": "routine", "ref_id": <routine_id>}},
    {{"time": "08:00", "duration_minutes": 90, "title": "<task title>", "type": "task", "ref_id": <task_id>}},
    {{"time": "09:30", "duration_minutes": 30, "title": "Pause + Spaziergang", "type": "break", "ref_id": null}},
    ...
  ],
  "daily_focus": "Ein Satz: Was ist der Kern-Fokus heute?"
}}

Regeln:
- Morgenroutinen zuerst (aus der Routinen-Liste, time_of_day=morning)
- Deep Work Block 08:00–12:00 für wichtigste Tasks (P1/P2)
- Mittagspause 12:00–13:00
- Nachmittags-Tasks 13:00–17:00
- Abendroutinen 18:00–21:00 (aus der Routinen-Liste, time_of_day=evening)
- Vermeide Überschneidungen mit gebuchten Terminen
- Nutze exakte IDs aus den Listen (ref_id muss integer sein oder null)
- type: "meal" | "task" | "routine" | "break"
- Jeden Task und jede Routine aus den Listen mindestens einmal einplanen
- Realistisch: max 6h produktive Arbeit"""

    try:
        resp = await _openai.chat.completions.create(
            model="gpt-4o-mini",
            response_format={"type": "json_object"},
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1200,
            temperature=0.2,
        )
        data = json.loads(resp.choices[0].message.content)
    except Exception:
        logger.exception("Day scheduler GPT failed for user %d", user.id)
        return [], ""

    schedule = data.get("schedule", [])
    daily_focus = str(data.get("daily_focus", ""))

    # Write work_block CalendarEvents for tasks and routines
    task_map = {t.id: t for t in tasks}
    routine_map = {r.id: r for r in routines}

    for entry in schedule:
        if not isinstance(entry, dict):
            continue
        entry_type = str(entry.get("type") or "")
        if entry_type not in ("task", "routine"):
            continue  # Don't store meals/breaks in DB

        time_str = str(entry.get("time") or "08:00")
        try:
            h, m = (int(x) for x in time_str.split(":")[:2])
        except Exception:
            continue

        duration = max(15, int(entry.get("duration_minutes") or 60))
        start_dt = _berlin_to_utc(datetime.combine(target_date, time(h, m)))
        end_dt = start_dt + timedelta(minutes=duration)

        ref_id = entry.get("ref_id")
        linked_task_id: Optional[int] = None
        linked_routine_id: Optional[int] = None
        title = str(entry.get("title") or "Block")[:200]

        if entry_type == "task" and ref_id and int(ref_id) in task_map:
            linked_task_id = int(ref_id)
            title = task_map[linked_task_id].title[:200]
        elif entry_type == "routine" and ref_id and int(ref_id) in routine_map:
            linked_routine_id = int(ref_id)
            title = routine_map[linked_routine_id].title[:200]

        ev = CalendarEvent(
            user_id=user.id,
            title=title,
            start_time=start_dt,
            end_time=end_dt,
            all_day=False,
            event_type="work_block",
            linked_task_id=linked_task_id,
            linked_routine_id=linked_routine_id,
            reminder_minutes_before=15,
        )
        session.add(ev)

    await session.flush()
    logger.info(
        "Day scheduler: generated %d blocks for user %d on %s",
        len([e for e in schedule if e.get("type") in ("task", "routine")]),
        user.id,
        target_date,
    )
    return schedule, daily_focus


def format_schedule_for_telegram(schedule: list[dict], daily_focus: str) -> str:
    """Format a schedule list into a Telegram-friendly string."""
    if not schedule:
        return ""

    TYPE_EMOJI = {
        "meal": "🍽",
        "task": "⚡",
        "routine": "🔄",
        "break": "☕",
    }

    lines = []
    if daily_focus:
        lines.append(f"🎯 _{daily_focus}_\n")

    lines.append("📅 *Tagesplan:*")
    for entry in schedule:
        t = entry.get("time", "?")
        title = entry.get("title", "")
        duration = entry.get("duration_minutes")
        etype = str(entry.get("type") or "")
        emoji = TYPE_EMOJI.get(etype, "•")
        dur_str = f" ({duration}min)" if duration else ""
        lines.append(f"{emoji} `{t}` {title}{dur_str}")

    return "\n".join(lines)
