"""Calendar event CRUD and iCal generation."""
import uuid
from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import CalendarEvent

_BERLIN = ZoneInfo("Europe/Berlin")
_UTC = ZoneInfo("UTC")


def _berlin_to_utc(dt: datetime) -> datetime:
    """Interpret a naive datetime as Europe/Berlin and convert to naive UTC for DB storage."""
    if dt.tzinfo is not None:
        return dt.astimezone(_UTC).replace(tzinfo=None)
    return dt.replace(tzinfo=_BERLIN).astimezone(_UTC).replace(tzinfo=None)


async def create_calendar_event(
    session: AsyncSession,
    user_id: int,
    title: str,
    start_time: str,
    event_type: str = "reminder",
    end_time: Optional[str] = None,
    all_day: bool = False,
    description: Optional[str] = None,
    linked_task_id: Optional[int] = None,
    linked_routine_id: Optional[int] = None,
) -> CalendarEvent:
    """Create a new calendar event. start_time can be YYYY-MM-DD HH:MM or YYYY-MM-DDTHH:MM."""
    formats = ["%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M", "%Y-%m-%d"]
    parsed_start = None
    for fmt in formats:
        try:
            parsed_start = datetime.strptime(start_time, fmt)
            break
        except ValueError:
            continue
    if not parsed_start:
        raise ValueError(f"Ungültiges Datum: {start_time}")
    # Convert Berlin local time to UTC for consistent DB storage
    parsed_start = _berlin_to_utc(parsed_start)

    parsed_end = None
    if end_time:
        for fmt in formats:
            try:
                parsed_end = datetime.strptime(end_time, fmt)
                break
            except ValueError:
                continue
        if parsed_end:
            parsed_end = _berlin_to_utc(parsed_end)

    event = CalendarEvent(
        user_id=user_id,
        title=title,
        description=description,
        start_time=parsed_start,
        end_time=parsed_end,
        all_day=all_day,
        event_type=event_type,
        linked_task_id=linked_task_id,
        linked_routine_id=linked_routine_id,
        ical_uid=f"{uuid.uuid4()}@personal-os",
    )
    session.add(event)
    await session.flush()
    return event


async def get_todays_events(session: AsyncSession, user_id: int) -> list[CalendarEvent]:
    """Get today's calendar events (Berlin timezone, stored as UTC)."""
    now_berlin = datetime.now(tz=_BERLIN)
    today_berlin = now_berlin.date()
    # Convert Berlin day boundaries to naive UTC for DB query
    today_start_utc = datetime.combine(today_berlin, datetime.min.time(), tzinfo=_BERLIN).astimezone(_UTC).replace(tzinfo=None)
    today_end_utc = datetime.combine(today_berlin, datetime.max.time(), tzinfo=_BERLIN).astimezone(_UTC).replace(tzinfo=None)

    result = await session.execute(
        select(CalendarEvent)
        .where(and_(
            CalendarEvent.user_id == user_id,
            CalendarEvent.start_time >= today_start_utc,
            CalendarEvent.start_time <= today_end_utc,
        ))
        .order_by(CalendarEvent.start_time)
    )
    return list(result.scalars().all())


async def get_upcoming_events(
    session: AsyncSession,
    user_id: int,
    days: int = 7,
    limit: int = 20,
) -> list[CalendarEvent]:
    """Get upcoming calendar events for a user."""
    now = datetime.utcnow()
    until = now + timedelta(days=days)
    result = await session.execute(
        select(CalendarEvent)
        .where(and_(
            CalendarEvent.user_id == user_id,
            CalendarEvent.start_time >= now,
            CalendarEvent.start_time <= until,
        ))
        .order_by(CalendarEvent.start_time)
        .limit(limit)
    )
    return list(result.scalars().all())


async def generate_ical_for_user(session: AsyncSession, user_id: int) -> str:
    """Generate complete iCal feed for a user."""
    result = await session.execute(
        select(CalendarEvent)
        .where(CalendarEvent.user_id == user_id)
        .order_by(CalendarEvent.start_time)
    )
    events = result.scalars().all()
    return generate_ical(list(events))


def generate_ical(events: list[CalendarEvent]) -> str:
    """Generate an iCal string from a list of CalendarEvents."""
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Personal OS//Personal OS 2.0//DE",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:Personal OS",
        "X-WR-TIMEZONE:Europe/Berlin",
    ]

    for event in events:
        dtstamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")

        if event.all_day:
            dtstart = f"VALUE=DATE:{event.start_time.strftime('%Y%m%d')}"
            if event.end_time:
                dtend = f"VALUE=DATE:{event.end_time.strftime('%Y%m%d')}"
            else:
                dtend = f"VALUE=DATE:{event.start_time.strftime('%Y%m%d')}"
            lines.extend([
                "BEGIN:VEVENT",
                f"UID:{event.ical_uid}",
                f"DTSTAMP:{dtstamp}",
                f"DTSTART;{dtstart}",
                f"DTEND;{dtend}",
                f"SUMMARY:{_ical_escape(event.title)}",
            ])
        else:
            dtstart = event.start_time.strftime("%Y%m%dT%H%M%SZ")
            if event.end_time:
                dtend = event.end_time.strftime("%Y%m%dT%H%M%SZ")
            else:
                dtend = (event.start_time + timedelta(hours=1)).strftime("%Y%m%dT%H%M%SZ")
            lines.extend([
                "BEGIN:VEVENT",
                f"UID:{event.ical_uid}",
                f"DTSTAMP:{dtstamp}",
                f"DTSTART:{dtstart}",
                f"DTEND:{dtend}",
                f"SUMMARY:{_ical_escape(event.title)}",
            ])

        if event.description:
            lines.append(f"DESCRIPTION:{_ical_escape(event.description)}")
        lines.extend([
            f"CATEGORIES:{event.event_type.upper()}",
            f"BEGIN:VALARM",
            f"TRIGGER:-PT{event.reminder_minutes_before}M",
            f"ACTION:DISPLAY",
            f"DESCRIPTION:Erinnerung: {_ical_escape(event.title)}",
            f"END:VALARM",
            "END:VEVENT",
        ])

    lines.append("END:VCALENDAR")
    return "\r\n".join(lines)


def _ical_escape(text: str) -> str:
    """Escape special characters for iCal."""
    return text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")
