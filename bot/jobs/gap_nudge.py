"""Gap nudge — detect free time windows and push the next priority task."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.db import get_session
from bot.database.models import CalendarEvent, Task, User

logger = logging.getLogger(__name__)

# Don't spam — track last nudge per user in memory (resets on restart, that's fine)
_last_nudge: dict[int, datetime] = {}
_MIN_INTERVAL_HOURS = 2


async def send_gap_nudges() -> None:
    """Check all active users for upcoming free windows and push next priority task."""
    try:
        async with get_session() as session:
            result = await session.execute(select(User))
            users = result.scalars().all()

            now = datetime.utcnow()
            hour = now.hour

            # Only during active hours (6–21 UTC ≈ 8–23 Berlin)
            if hour < 6 or hour >= 21:
                return

            for user in users:
                try:
                    await _nudge_user(session, user, now)
                except Exception as e:
                    logger.warning("Gap nudge failed user %d: %s", user.id, e)
    except Exception as e:
        logger.error("send_gap_nudges error: %s", e)


async def _nudge_user(session: AsyncSession, user: User, now: datetime) -> None:
    from bot.telegram.sender import send_message

    # Rate limit — don't nudge more than once every 2 hours
    last = _last_nudge.get(user.id)
    if last and (now - last).total_seconds() < _MIN_INTERVAL_HOURS * 3600:
        return

    # Check if there's a calendar event starting in the next 90 min
    window_end = now + timedelta(minutes=90)
    conflict = await session.execute(
        select(CalendarEvent).where(
            and_(
                CalendarEvent.user_id == user.id,
                CalendarEvent.start_time >= now,
                CalendarEvent.start_time <= window_end,
            )
        ).limit(1)
    )
    upcoming_event = conflict.scalar_one_or_none()

    # Find highest priority open task
    tasks_result = await session.execute(
        select(Task).where(
            and_(
                Task.user_id == user.id,
                Task.status == "open",
            )
        ).order_by(Task.priority, Task.created_at).limit(1)
    )
    top_task = tasks_result.scalar_one_or_none()

    if not top_task:
        return  # Nothing to push

    if upcoming_event:
        # Upcoming meeting in < 90 min — prep nudge
        mins = int((upcoming_event.start_time - now).total_seconds() / 60)
        if mins > 60:
            return  # Too far ahead, skip
        msg = (
            f"📅 *{upcoming_event.title}* in {mins} Minuten\n\n"
            f"Schnell davor noch:\n☐ *{top_task.title}*"
        )
    else:
        # Free window — push top task
        msg = (
            f"⚡ *Freies Zeitfenster!*\n\n"
            f"Deine Top-Priorität jetzt:\n"
            f"☐ *{top_task.title}*"
        )
        if top_task.due_date:
            msg += f"\n📅 Fällig: {top_task.due_date.strftime('%d.%m.')}"
        msg += "\n\nAntworte *'erledigt'* wenn fertig."

    try:
        await send_message(user.telegram_id, msg, parse_mode="Markdown")
        _last_nudge[user.id] = now
        logger.info("Gap nudge sent to user %d", user.id)
    except Exception as e:
        logger.warning("send_message failed for user %d: %s", user.id, e)
