"""Plan coherence: daily conflict detection, morning brief, weekly kickoff, evening preview."""
import logging
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import CalendarEvent, User

logger = logging.getLogger(__name__)

_BERLIN = ZoneInfo("Europe/Berlin")
_UTC = ZoneInfo("UTC")

# Event types where an overlap with a social/external event is an actual conflict
_FLEXIBLE_TYPES = {"routine", "reminder", "errand", "work_block"}
_FIXED_TYPES = {"meeting", "training", "travel", "deadline"}

# Reminder events that become irrelevant when a real event is happening
_SUPERSEDED_KEYWORDS = ["freier abend", "kein handy", "kein work", "abschalten"]


def _utc_to_berlin(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_UTC)
    return dt.astimezone(_BERLIN)


def _get_day_bounds_utc(target_date: date) -> tuple[datetime, datetime]:
    start_berlin = datetime(target_date.year, target_date.month, target_date.day, 0, 0, tzinfo=_BERLIN)
    end_berlin = datetime(target_date.year, target_date.month, target_date.day, 23, 59, tzinfo=_BERLIN)
    return (
        start_berlin.astimezone(_UTC).replace(tzinfo=None),
        end_berlin.astimezone(_UTC).replace(tzinfo=None),
    )


async def get_day_events(session: AsyncSession, user_id: int, target_date: date) -> list[CalendarEvent]:
    start_utc, end_utc = _get_day_bounds_utc(target_date)
    result = await session.execute(
        select(CalendarEvent)
        .where(and_(
            CalendarEvent.user_id == user_id,
            CalendarEvent.start_time >= start_utc,
            CalendarEvent.start_time <= end_utc,
        ))
        .order_by(CalendarEvent.start_time)
    )
    return list(result.scalars().all())


def detect_conflicts(events: list[CalendarEvent]) -> list[dict]:
    """Detect overlapping events and logically superseded reminders."""
    conflicts = []

    for i, a in enumerate(events):
        a_start = _utc_to_berlin(a.start_time)
        a_end = _utc_to_berlin(a.end_time) if a.end_time else a_start + timedelta(minutes=30)

        for b in events[i + 1:]:
            b_start = _utc_to_berlin(b.start_time)
            b_end = _utc_to_berlin(b.end_time) if b.end_time else b_start + timedelta(minutes=30)

            # Check overlap
            if a_start < b_end and a_end > b_start:
                # Check if one is flexible and the other is fixed
                a_fixed = a.event_type in _FIXED_TYPES
                b_fixed = b.event_type in _FIXED_TYPES

                # Social/external event supersedes a "Freier Abend" style reminder
                if b_fixed and any(kw in (a.title or "").lower() for kw in _SUPERSEDED_KEYWORDS):
                    conflicts.append({
                        "type": "superseded",
                        "flexible": a,
                        "fixed": b,
                        "msg": (
                            f"⚠️ *{a.title}* ({a_start.strftime('%H:%M')}–{a_end.strftime('%H:%M')}) "
                            f"überschneidet sich mit *{b.title}* ({b_start.strftime('%H:%M')}–{b_end.strftime('%H:%M')})"
                        ),
                    })
                elif a_fixed and any(kw in (b.title or "").lower() for kw in _SUPERSEDED_KEYWORDS):
                    conflicts.append({
                        "type": "superseded",
                        "flexible": b,
                        "fixed": a,
                        "msg": (
                            f"⚠️ *{b.title}* ({b_start.strftime('%H:%M')}–{b_end.strftime('%H:%M')}) "
                            f"überschneidet sich mit *{a.title}* ({a_start.strftime('%H:%M')}–{a_end.strftime('%H:%M')})"
                        ),
                    })
                elif a_fixed and b_fixed:
                    # Two hard events overlapping
                    conflicts.append({
                        "type": "hard_conflict",
                        "a": a,
                        "b": b,
                        "msg": (
                            f"🚨 *{a.title}* ({a_start.strftime('%H:%M')}–{a_end.strftime('%H:%M')}) "
                            f"und *{b.title}* ({b_start.strftime('%H:%M')}–{b_end.strftime('%H:%M')}) "
                            f"überlappen!"
                        ),
                    })

    return conflicts


def format_day_plan(target_date: date, events: list[CalendarEvent], conflicts: list[dict]) -> str:
    """Format a clean day overview with conflict warnings."""
    weekdays = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
    day_name = weekdays[target_date.weekday()]
    date_str = target_date.strftime("%d.%m.")

    type_emoji = {
        "training": "💪", "meeting": "🤝", "routine": "🔄",
        "deadline": "⏰", "reminder": "🔔", "errand": "📍",
        "work_block": "🧠", "travel": "✈️",
    }

    lines = [f"📅 *{day_name}, {date_str}*\n"]
    for e in events:
        start = _utc_to_berlin(e.start_time).strftime("%H:%M")
        end = _utc_to_berlin(e.end_time).strftime("%H:%M") if e.end_time else ""
        time_str = f"{start}–{end}" if end else start
        emoji = type_emoji.get(e.event_type, "📌")
        lines.append(f"{emoji} {time_str} {e.title}")

    if conflicts:
        lines.append("\n⚠️ *Ungereimtheiten erkannt:*")
        for c in conflicts:
            lines.append(c["msg"])
        lines.append("\nSoll ich das bereinigen? Einfach antworten was du willst.")

    return "\n".join(lines)


def format_week_overview(
    week_start: date, days_events: dict[date, list[CalendarEvent]]
) -> str:
    """Format a week overview message."""
    weekdays = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
    type_emoji = {
        "training": "💪", "meeting": "🤝", "routine": "🔄",
        "deadline": "⏰", "reminder": "🔔", "errand": "📍",
        "work_block": "🧠", "travel": "✈️",
    }
    lines = [
        f"🗓 *Wochenplan — KW {week_start.strftime('%V')}*\n",
        f"Woche vom {week_start.strftime('%d.%m.')} bis {(week_start + timedelta(days=6)).strftime('%d.%m.')}\n",
    ]

    for i in range(7):
        day = week_start + timedelta(days=i)
        events = days_events.get(day, [])
        # Filter out pure routine events to keep overview concise
        key_events = [e for e in events if e.event_type not in ("routine",)]
        dow = weekdays[i]
        date_str = day.strftime("%d.%m.")

        if not key_events:
            lines.append(f"*{dow} {date_str}* — frei ✨")
        else:
            event_parts = []
            for e in key_events[:4]:
                start = _utc_to_berlin(e.start_time).strftime("%H:%M")
                emoji = type_emoji.get(e.event_type, "📌")
                event_parts.append(f"{emoji} {start} {e.title}")
            suffix = f" +{len(key_events) - 4} weitere" if len(key_events) > 4 else ""
            lines.append(f"*{dow} {date_str}*")
            for ep in event_parts:
                lines.append(f"  {ep}")
            if suffix:
                lines.append(f"  _{suffix}_")

        lines.append("")

    lines.append("Passt die Woche so? Soll ich irgendwo was anpassen?")
    return "\n".join(lines)


async def send_morning_plan_brief(bot, user: User, session: AsyncSession) -> None:
    """Send today's plan overview with conflict detection. Called after morning context."""
    from bot.jobs.reminders import _already_reminded, _mark_reminder
    from bot.database.connection import get_session  # noqa – session already provided
    from zoneinfo import ZoneInfo
    now_berlin = datetime.now(tz=ZoneInfo("Europe/Berlin"))
    today = now_berlin.date()
    today_start = datetime.combine(today, datetime.min.time())

    reminder_type = "morning_plan_brief"
    if await _already_reminded(session, user.id, reminder_type, today_start):
        return

    events = await get_day_events(session, user.id, today)
    if not events:
        return

    conflicts = detect_conflicts(events)
    text = format_day_plan(today, events, conflicts)

    try:
        await bot.send_message(chat_id=user.telegram_id, text=text, parse_mode="Markdown")
        await _mark_reminder(session, user.id, reminder_type, text[:200])
    except Exception:
        logger.exception("Failed to send morning plan brief to user %s", user.id)


async def send_tomorrow_preview(bot, user: User, session: AsyncSession) -> None:
    """Send tomorrow's calendar preview. Called at end of evening check-in."""
    from bot.jobs.reminders import _already_reminded, _mark_reminder
    from zoneinfo import ZoneInfo
    now_berlin = datetime.now(tz=ZoneInfo("Europe/Berlin"))
    today = now_berlin.date()
    tomorrow = today + timedelta(days=1)
    today_start = datetime.combine(today, datetime.min.time())

    reminder_type = "tomorrow_preview"
    if await _already_reminded(session, user.id, reminder_type, today_start):
        return

    events = await get_day_events(session, user.id, tomorrow)
    if not events:
        return

    conflicts = detect_conflicts(events)
    text = "👀 *Blick auf morgen:*\n\n" + format_day_plan(tomorrow, events, conflicts)

    try:
        await bot.send_message(chat_id=user.telegram_id, text=text, parse_mode="Markdown")
        await _mark_reminder(session, user.id, reminder_type, text[:200])
    except Exception:
        logger.exception("Failed to send tomorrow preview to user %s", user.id)


async def send_weekly_kickoff(bot, user: User, session: AsyncSession) -> None:
    """Send Monday morning week overview. Called from scheduler on Mondays."""
    from bot.jobs.reminders import _already_reminded, _mark_reminder
    from zoneinfo import ZoneInfo
    now_berlin = datetime.now(tz=ZoneInfo("Europe/Berlin"))
    today = now_berlin.date()
    today_start = datetime.combine(today, datetime.min.time())

    # Only run on Mondays
    if today.weekday() != 0:
        return

    reminder_type = "weekly_kickoff"
    if await _already_reminded(session, user.id, reminder_type, today_start):
        return

    # Collect all events for Mon–Sun
    days_events: dict[date, list[CalendarEvent]] = {}
    for i in range(7):
        day = today + timedelta(days=i)
        days_events[day] = await get_day_events(session, user.id, day)

    # Detect conflicts across all days
    all_conflicts = []
    for day, events in days_events.items():
        all_conflicts.extend(detect_conflicts(events))

    text = format_week_overview(today, days_events)

    if all_conflicts:
        conflict_lines = ["\n⚠️ *Konflikte diese Woche:*"]
        for c in all_conflicts[:5]:
            conflict_lines.append(c["msg"])
        text += "\n" + "\n".join(conflict_lines)

    try:
        await bot.send_message(chat_id=user.telegram_id, text=text, parse_mode="Markdown")
        await _mark_reminder(session, user.id, reminder_type, "weekly_kickoff")
    except Exception:
        logger.exception("Failed to send weekly kickoff to user %s", user.id)


async def run_weekly_kickoff() -> None:
    """Scheduler job: Monday morning week overview for all active users."""
    from bot.telegram.sender import get_bot
    from bot.database.connection import get_session
    from bot.database.models import User
    bot = get_bot()

    async with get_session() as session:
        result = await session.execute(select(User).where(User.is_active == True))  # noqa: E712
        users = result.scalars().all()
        for user in users:
            s = user.settings or {}
            if not s.get("proactive_enabled", True):
                continue
            try:
                await send_weekly_kickoff(bot, user, session)
            except Exception:
                logger.exception("Weekly kickoff failed for user %s", user.id)
