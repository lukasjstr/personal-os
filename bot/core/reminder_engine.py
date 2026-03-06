"""CORE-5a/5c: Reminder execution loop with persistence helpers.

Responsibilities:
- Select due reminders from stored ScheduledReminder rows
- Apply quiet-hours gate
- Batch reminders per user (BATCH_SIZE cap)
- Retry policy: escalating backoff, dead-letter after MAX_ATTEMPTS
- dry_run_preview(): returns what would be sent at a given now-time (no DB writes)
- mark_sent(): persist sent state on success
- mark_failed(): increment retry_count, persist next_retry_at on failure
- mark_dead_letter(): move to failed/dead-letter state when MAX_ATTEMPTS exceeded
"""

from __future__ import annotations

import dataclasses
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import and_, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from bot.core.reminder_factory import ReminderConfig, _is_in_quiet_hours
from bot.database.models import ScheduledReminder

# ── Retry policy constants ────────────────────────────────────────────────────
MAX_ATTEMPTS: int = 3
RETRY_BACKOFF_MINUTES: list[int] = [5, 15, 60]  # escalating back-off per attempt

# Max reminders dispatched per engine tick per user
BATCH_SIZE: int = 20

# reminder_type values that get high priority (1)
_HIGH_PRIORITY_TYPES: frozenset[str] = frozenset(
    {"task_deadline", "calendar_prep", "streak_warning"}
)


@dataclasses.dataclass
class DueReminder:
    """Lightweight view of a reminder that the engine would dispatch."""

    id: Optional[int]                      # DB row id; None for in-memory draft placeholders
    user_id: int
    reminder_type: str                     # mirrors ScheduledReminder.reminder_type
    message: str
    scheduled_for: datetime
    priority: int                          # 1=high, 2=medium, 3=low
    source: str                            # "db" | "draft"
    retry_attempt: int = 0                 # mirrors retry_count from DB row
    next_retry_at: Optional[datetime] = None  # persisted next_retry_at from DB row
    quiet_hours_blocked: bool = False      # True if suppressed by quiet-hours gate


@dataclasses.dataclass
class EnginePreviewResult:
    """Result returned by dry_run_preview() — pure data, no side-effects."""

    now: datetime
    config: ReminderConfig
    total_due: int            # reminders whose scheduled_for <= now
    quiet_hours_blocked: int  # count suppressed by quiet-hours gate
    would_send: list[DueReminder]
    batch_size: int


# ── Public API ────────────────────────────────────────────────────────────────


async def dry_run_preview(
    session: AsyncSession,
    user_id: int,
    now: datetime,
    config: Optional[ReminderConfig] = None,
) -> EnginePreviewResult:
    """Return what the execution loop would send at *now*, without any DB writes.

    Steps:
      1. Select pending ScheduledReminder rows with scheduled_for <= now  (read-only)
      2. Apply quiet-hours gate — reminders in quiet hours are flagged, not dropped
      3. Filter to sendable (non-blocked) and cap at BATCH_SIZE, priority-first

    No rows are mutated, no messages are sent.
    """
    if config is None:
        config = ReminderConfig()

    # 1. Select due candidates (read-only DB query)
    rows = await _select_due_reminders(session, user_id, now)

    # 2. Map to DueReminder, apply quiet-hours gate
    candidates: list[DueReminder] = []
    blocked_count = 0
    for row in rows:
        in_quiet = _is_in_quiet_hours(row.scheduled_for, config)
        priority = 1 if row.reminder_type in _HIGH_PRIORITY_TYPES else 2
        candidates.append(
            DueReminder(
                id=row.id,
                user_id=row.user_id,
                reminder_type=row.reminder_type,
                message=row.message,
                scheduled_for=row.scheduled_for,
                priority=priority,
                source="db",
                retry_attempt=row.retry_count,
                next_retry_at=row.next_retry_at,
                quiet_hours_blocked=in_quiet,
            )
        )
        if in_quiet:
            blocked_count += 1

    # 3. Filter blocked, sort by priority then time, cap at BATCH_SIZE
    sendable = [r for r in candidates if not r.quiet_hours_blocked]
    batch = _apply_batch(sendable, BATCH_SIZE)

    return EnginePreviewResult(
        now=now,
        config=config,
        total_due=len(candidates),
        quiet_hours_blocked=blocked_count,
        would_send=batch,
        batch_size=len(batch),
    )


# ── Internal helpers ──────────────────────────────────────────────────────────


async def _select_due_reminders(
    session: AsyncSession,
    user_id: int,
    now: datetime,
) -> list[ScheduledReminder]:
    """Select pending ScheduledReminder rows with scheduled_for <= now.

    Over-fetches by 2x BATCH_SIZE to leave room for quiet-hours filtering.
    Phase 5b will extend this to include persisted ReminderDraft rows once
    a storage table for drafts exists.
    """
    result = await session.execute(
        select(ScheduledReminder)
        .where(
            and_(
                ScheduledReminder.user_id == user_id,
                ScheduledReminder.status == "pending",
                ScheduledReminder.scheduled_for <= now,
                or_(
                    ScheduledReminder.next_retry_at == None,  # noqa: E711
                    ScheduledReminder.next_retry_at <= now,
                ),
            )
        )
        .order_by(ScheduledReminder.scheduled_for)
        .limit(BATCH_SIZE * 2)
    )
    return list(result.scalars().all())


def _apply_batch(reminders: list[DueReminder], batch_size: int) -> list[DueReminder]:
    """Return at most *batch_size* reminders, highest priority first, then earliest first."""
    sorted_reminders = sorted(reminders, key=lambda r: (r.priority, r.scheduled_for))
    return sorted_reminders[:batch_size]


def retry_delay_minutes(attempt: int) -> Optional[int]:
    """Return minutes to wait before the next retry, or None if max attempts reached.

    attempt=0 → first retry after 5 min
    attempt=1 → second retry after 15 min
    attempt=2 → third retry after 60 min (MAX_ATTEMPTS - 1)
    attempt>=3 → None (give up)
    """
    if attempt >= MAX_ATTEMPTS:
        return None
    return RETRY_BACKOFF_MINUTES[attempt]


# ── Persistence helpers ───────────────────────────────────────────────────────


async def mark_sent(session: AsyncSession, row_id: int, now: datetime) -> None:
    """Mark a ScheduledReminder as successfully sent."""
    await session.execute(
        update(ScheduledReminder)
        .where(ScheduledReminder.id == row_id)
        .values(status="sent", sent_at=now)
    )
    await session.commit()


async def mark_failed(
    session: AsyncSession,
    row_id: int,
    now: datetime,
    current_retry_count: int,
) -> None:
    """Increment retry_count and schedule next_retry_at using escalating backoff.

    Only call this when current_retry_count + 1 < MAX_ATTEMPTS (i.e. retries remain).
    Use mark_dead_letter() when the attempt ceiling is reached.
    """
    new_count = current_retry_count + 1
    delay = retry_delay_minutes(current_retry_count)  # index = current count
    next_retry = now + timedelta(minutes=delay) if delay is not None else None
    await session.execute(
        update(ScheduledReminder)
        .where(ScheduledReminder.id == row_id)
        .values(retry_count=new_count, next_retry_at=next_retry)
    )
    await session.commit()


async def mark_dead_letter(session: AsyncSession, row_id: int) -> None:
    """Set status='failed' (dead-letter) — no further retries will be attempted."""
    await session.execute(
        update(ScheduledReminder)
        .where(ScheduledReminder.id == row_id)
        .values(status="failed")
    )
    await session.commit()


# ── Telegram sender helper ────────────────────────────────────────────────────


async def send_telegram(telegram_id: int, message: str) -> bool:
    """Send *message* to *telegram_id* via the bot.  Returns True on success."""
    from bot.telegram.sender import send_message  # deferred import avoids circular

    return await send_message(telegram_id, message)
