"""Calendar event CRUD and iCal generation."""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import CalendarEvent


async def create_calendar_event(
    session: AsyncSession,
    user_id: int,
    title: str,
    start_time: str,
    event_type: str,
    end_time: Optional[str] = None,
    description: Optional[str] = None,
    linked_task_id: Optional[int] = None,
    linked_routine_id: Optional[int] = None,
) -> CalendarEvent:
    """Create a new calendar event."""
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

    parsed_end = None
    if end_time:
        for fmt in formats:
            try:
                parsed_end = datetime.strptime(end_time, fmt)
                break
            except ValueError:
                continue

    event = CalendarEvent(
        user_id=user_id,
        title=title,
        description=description,
        start_time=parsed_start,
        end_time=parsed_end,
        event_type=event_type,
        linked_task_id=linked_task_id,
        linked_routine_id=linked_routine_id,
        ical_uid=f"{uuid.uuid4()}@personal-os",
    )
    session.add(event)
    await session.flush()
    return event


async def get_upcoming_events(
    session: AsyncSession,
    user_id: int,
    limit: int = 10,
) -> list[CalendarEvent]:
    """Get upcoming calendar events for a user."""
    now = datetime.utcnow()
    result = await session.execute(
        select(CalendarEvent)
        .where(
            and_(
                CalendarEvent.user_id == user_id,
                CalendarEvent.start_time >= now,
            )
        )
        .order_by(CalendarEvent.start_time)
        .limit(limit)
    )
    return result.scalars().all()


def generate_ical(events: list[CalendarEvent], user_token: str) -> str:
    """Generate an iCal string from a list of CalendarEvents."""
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Personal OS//Personal OS 1.0//DE",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:Personal OS",
        "X-WR-TIMEZONE:Europe/Berlin",
    ]

    for event in events:
        dtstart = event.start_time.strftime("%Y%m%dT%H%M%SZ")
        if event.end_time:
            dtend = event.end_time.strftime("%Y%m%dT%H%M%SZ")
        else:
            # Default 1 hour
            from datetime import timedelta
            dtend = (event.start_time + timedelta(hours=1)).strftime("%Y%m%dT%H%M%SZ")

        dtstamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
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
            "END:VEVENT",
        ])

    lines.append("END:VCALENDAR")
    return "\r\n".join(lines)


def _ical_escape(text: str) -> str:
    """Escape special characters for iCal."""
    return text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")
