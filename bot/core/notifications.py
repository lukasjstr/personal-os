"""Notification pipeline helpers.

Provides enqueue_notification() — the single entry point for creating
AutopilotNotification rows with:
  - Quiet-hours guard (Berlin timezone)
  - Anti-spam dedup (same type+body within last 60 min → skip)
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import AutopilotNotification


# Berlin UTC offset — simplified to +1 (CET).  DST transitions are rare
# and a ±1 hour inaccuracy during switchover is acceptable.
_BERLIN_OFFSET = timedelta(hours=1)


def _berlin_hour() -> int:
    """Return the current hour in Berlin time (CET, UTC+1)."""
    return (datetime.now(tz=timezone.utc) + _BERLIN_OFFSET).hour


def _in_quiet_window(hour: int, quiet_start: int, quiet_end: int) -> bool:
    """Return True if *hour* falls within the overnight quiet window.

    quiet_start=22 / quiet_end=8 means 22:00 → 07:59 is quiet.
    Works correctly when start > end (window crosses midnight).
    """
    if quiet_start > quiet_end:          # crosses midnight
        return hour >= quiet_start or hour < quiet_end
    return quiet_start <= hour < quiet_end  # same-day window


async def enqueue_notification(
    session: AsyncSession,
    user_id: int,
    notification_type: str,
    body: str,
    title: Optional[str] = None,
    metadata: Optional[dict] = None,
    linked_task_id: Optional[int] = None,
    source: str = "autopilot",
    quiet_hour_start: int = 22,
    quiet_hour_end: int = 8,
    dedup_window_minutes: int = 60,
) -> Optional[AutopilotNotification]:
    """Create and persist an AutopilotNotification with quiet-hours and dedup guards.

    Returns the new notification row, or None if the notification was skipped.
    """
    # ── 1. Quiet-hours check ───────────────────────────────────────────────
    current_hour = _berlin_hour()
    if _in_quiet_window(current_hour, quiet_hour_start, quiet_hour_end):
        return None

    # ── 2. Anti-spam dedup ─────────────────────────────────────────────────
    since = datetime.now(tz=timezone.utc).replace(tzinfo=None) - timedelta(
        minutes=dedup_window_minutes
    )
    existing = await session.execute(
        select(AutopilotNotification).where(
            and_(
                AutopilotNotification.user_id == user_id,
                AutopilotNotification.notification_type == notification_type,
                AutopilotNotification.body == body,
                AutopilotNotification.status.in_(["pending", "snoozed"]),
                AutopilotNotification.created_at >= since,
            )
        )
    )
    if existing.scalar_one_or_none() is not None:
        return None

    # ── 3. Insert ──────────────────────────────────────────────────────────
    notif = AutopilotNotification(
        user_id=user_id,
        notification_type=notification_type,
        title=title or notification_type.replace("_", " ").title(),
        body=body,
        status="pending",
        source=source,
        linked_task_id=linked_task_id,
    )
    session.add(notif)
    await session.flush()
    return notif
