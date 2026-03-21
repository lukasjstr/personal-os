"""iCal sync — fetch Google Calendar ICS and upsert into calendar_events."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

import httpx
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.connection import get_session
from bot.database.models import CalendarEvent, User

logger = logging.getLogger(__name__)


def _parse_dt(dt_val) -> Optional[datetime]:
    """Convert icalendar date/datetime to UTC datetime."""
    if dt_val is None:
        return None
    if hasattr(dt_val, "dt"):
        dt_val = dt_val.dt
    if isinstance(dt_val, datetime):
        if dt_val.tzinfo is None:
            return dt_val
        return dt_val.astimezone(timezone.utc).replace(tzinfo=None)
    # date only → midnight
    return datetime(dt_val.year, dt_val.month, dt_val.day, 0, 0, 0)


async def sync_ical_for_user(session: AsyncSession, user: User) -> int:
    """Fetch and sync iCal events for a user. Returns count of new events."""
    if not user.ical_url:
        return 0
    try:
        from icalendar import Calendar  # type: ignore
    except ImportError:
        logger.error("icalendar not installed — run: pip install icalendar")
        return 0

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(user.ical_url, follow_redirects=True)
            resp.raise_for_status()
            cal = Calendar.from_ical(resp.content)
    except Exception as e:
        logger.warning("iCal fetch failed for user %d: %s", user.id, e)
        return 0

    now = datetime.utcnow()
    cutoff_past = datetime(now.year, now.month, 1)
    cutoff_future = datetime(now.year + 1, now.month, now.day)

    count = 0
    for component in cal.walk():
        if component.name != "VEVENT":
            continue
        uid = str(component.get("UID", "")).strip()
        if not uid:
            continue
        summary = str(component.get("SUMMARY", "Termin")).strip()
        dtstart = _parse_dt(component.get("DTSTART"))
        dtend = _parse_dt(component.get("DTEND"))
        description = str(component.get("DESCRIPTION", "") or "").strip() or None

        if not dtstart:
            continue
        if dtstart < cutoff_past or dtstart > cutoff_future:
            continue

        existing_result = await session.execute(
            select(CalendarEvent).where(
                and_(
                    CalendarEvent.user_id == user.id,
                    CalendarEvent.external_id == uid,
                )
            )
        )
        all_existing = existing_result.scalars().all()
        # Clean up duplicates: keep first, delete rest
        if len(all_existing) > 1:
            for dup in all_existing[1:]:
                await session.delete(dup)
        existing = all_existing[0] if all_existing else None

        if existing:
            existing.title = summary
            existing.start_time = dtstart
            existing.end_time = dtend
            existing.description = description
        else:
            event = CalendarEvent(
                user_id=user.id,
                title=summary,
                start_time=dtstart,
                end_time=dtend,
                description=description,
                event_type="meeting",
                external_id=uid,
                external_source="ical",
            )
            session.add(event)
            count += 1

    await session.flush()
    logger.info("iCal sync: %d new events for user %d", count, user.id)
    return count


async def sync_all_users() -> None:
    """Sync iCal for all users with ical_url configured."""
    try:
        async with get_session() as session:
            result = await session.execute(
                select(User).where(User.ical_url.isnot(None))
            )
            users = result.scalars().all()
            for user in users:
                try:
                    await sync_ical_for_user(session, user)
                except Exception as e:
                    logger.error("iCal sync error user %d: %s", user.id, e)
    except Exception as e:
        logger.error("iCal sync_all_users failed: %s", e)
