"""Calendar event CRUD and iCal generation."""
import logging
import re
import uuid
from datetime import date, datetime, time, timedelta
from typing import Iterable, Optional
from zoneinfo import ZoneInfo

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import CalendarEvent, Routine

logger = logging.getLogger(__name__)

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


# ─── V3 P04 — Routine expansion into calendar events ────────────────────────

_WEEKDAY_DE: dict[str, int] = {
    # Monday=0 .. Sunday=6 (matches date.weekday())
    "mo": 0, "mon": 0, "montag": 0,
    "di": 1, "die": 1, "dienstag": 1,
    "mi": 2, "mit": 2, "mittwoch": 2,
    "do": 3, "don": 3, "donnerstag": 3,
    "fr": 4, "fre": 4, "freitag": 4,
    "sa": 5, "sam": 5, "samstag": 5,
    "so": 6, "son": 6, "sonntag": 6,
}

_TIME_OF_DAY_HOUR: dict[str, int] = {
    "morning": 7,
    "midday": 12,
    "evening": 19,
    "anytime": 8,
}


def parse_frequency_human(freq: str) -> set[int]:
    """Parse a German/English routine frequency string into weekday integers (0=Mon..6=Sun).

    Examples:
        'Täglich'           → {0,1,2,3,4,5,6}
        'Daily'             → {0,1,2,3,4,5,6}
        'Mo/Mi/Fr'          → {0, 2, 4}
        'Jeden Dienstag'    → {1}
        'wöchentlich'       → {0}            (default Monday)
        'weekly'            → {0}
        '3x pro Woche'      → {0, 2, 4}      (heuristic: Mo/Mi/Fr)
        ''                  → {0}

    Returns an empty set only if explicitly given an empty-meaning value
    that we can't interpret.
    """
    if not freq:
        return {0}
    s = freq.strip().lower()
    if any(k in s for k in ("täglich", "taglich", "daily", "jeden tag")):
        return {0, 1, 2, 3, 4, 5, 6}

    # explicit weekday tokens (split on "/", ",", "+", spaces)
    tokens = [t.strip(".") for t in re.split(r"[\s,/+]+", s) if t.strip()]
    weekdays: set[int] = set()
    for tok in tokens:
        if tok in _WEEKDAY_DE:
            weekdays.add(_WEEKDAY_DE[tok])
        else:
            # match longer words like "donnerstag"
            for key, wd in _WEEKDAY_DE.items():
                if len(key) >= 3 and key in tok:
                    weekdays.add(wd)
                    break
    if weekdays:
        return weekdays

    # heuristic: '3x pro Woche' → Mo/Mi/Fr, '2x' → Di/Do, '5x' → Mo–Fr
    m = re.search(r"(\d+)\s*[x×]", s)
    if m:
        n = int(m.group(1))
        if n == 1:
            return {0}
        if n == 2:
            return {1, 3}
        if n == 3:
            return {0, 2, 4}
        if n == 4:
            return {0, 2, 4, 5}
        if n >= 5:
            return {0, 1, 2, 3, 4}

    if "woch" in s or "weekly" in s:
        return {0}

    # Last resort: default Monday
    return {0}


async def expand_routine_to_calendar(
    session: AsyncSession,
    routine: Routine,
    weeks_ahead: int = 4,
    start_date: Optional[date] = None,
) -> list[int]:
    """Materialize a Routine as concrete CalendarEvent rows.

    Idempotent: events are keyed by `ical_uid=f"routine-{routine.id}-{YYYY-MM-DD}@personal-os"`.
    Re-running this skips already-created dates.

    Returns the list of CalendarEvent ids that exist for this routine within
    the window (newly created + already-present).
    """
    if start_date is None:
        start_date = date.today()
    weekdays = parse_frequency_human(routine.frequency_human or "")
    if not weekdays:
        logger.warning("Routine %d has unparseable frequency '%s' — skip expansion",
                       routine.id, routine.frequency_human)
        return []

    hour = _TIME_OF_DAY_HOUR.get((routine.time_of_day or "anytime").lower(), 8)
    horizon = start_date + timedelta(days=weeks_ahead * 7)
    created_or_existing: list[int] = []

    # Pre-load existing routine events in window to avoid one query per date
    existing_res = await session.execute(
        select(CalendarEvent).where(and_(
            CalendarEvent.linked_routine_id == routine.id,
            CalendarEvent.start_time >= datetime.combine(start_date, time.min),
            CalendarEvent.start_time < datetime.combine(horizon, time.min),
        ))
    )
    existing_by_date: dict[date, CalendarEvent] = {
        ev.start_time.date(): ev for ev in existing_res.scalars().all()
    }

    d = start_date
    while d < horizon:
        if d.weekday() in weekdays:
            if d in existing_by_date:
                created_or_existing.append(existing_by_date[d].id)
            else:
                start_dt = datetime.combine(d, time(hour=hour, minute=0))
                end_dt = start_dt + timedelta(minutes=30)
                ical_uid = f"routine-{routine.id}-{d.isoformat()}@personal-os"
                ev = CalendarEvent(
                    user_id=routine.user_id,
                    title=routine.title,
                    description=f"Routine#{routine.id} — {routine.frequency_human}",
                    start_time=start_dt,
                    end_time=end_dt,
                    all_day=False,
                    event_type="routine",
                    linked_routine_id=routine.id,
                    ical_uid=ical_uid,
                )
                session.add(ev)
                try:
                    await session.flush()
                    created_or_existing.append(ev.id)
                except Exception:
                    # ical_uid collision — another expansion ran concurrently. Skip.
                    await session.rollback()
                    logger.info("Routine expansion: skipping duplicate uid=%s", ical_uid)
        d += timedelta(days=1)

    return created_or_existing
