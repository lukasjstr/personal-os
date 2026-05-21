# TODO: AUDIT-2026-05 — DEAD CODE (no importers, 252 LOC). Logic lives in reminder_engine.py. See docs/AUDIT-2026-05.md.
"""CORE-5b/5d: Due reminder processor loop — fetches, gates, sends, persists.

Responsibilities:
- Fetch all distinct user IDs that have pending reminders due at *now*
- For each user: delegate per-user batching + quiet-hours gate to reminder_engine
- Apply retry backoff gate (next_retry_at enforced at DB level)
- Send each dispatchable reminder via Telegram
- Persist outcome: mark_sent on success; mark_failed (schedules retry) or
  mark_dead_letter (MAX_ATTEMPTS exceeded) on failure
- Produce a ProcessorTickResult summary per tick
"""

from __future__ import annotations

import dataclasses
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import distinct, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.core.reminder_engine import (
    BATCH_SIZE,
    MAX_ATTEMPTS,
    DueReminder,
    EnginePreviewResult,
    dry_run_preview,
    mark_dead_letter,
    mark_failed,
    mark_sent,
    retry_delay_minutes,
    send_telegram,
)
from bot.core.reminder_factory import ReminderConfig
from bot.database.models import ScheduledReminder, User


# ── Processor-level policy constants ─────────────────────────────────────────

# Maximum users processed in a single scheduler tick (safety cap)
MAX_USERS_PER_TICK: int = 50


# ── Result types ──────────────────────────────────────────────────────────────


@dataclasses.dataclass
class UserTickResult:
    """Per-user outcome within a single processor tick."""

    user_id: int
    engine_result: EnginePreviewResult
    # Subset of would_send that pass the retry-backoff gate
    dispatchable: list[DueReminder]
    # Items skipped because simulated next_retry_at > now
    retry_deferred: list[DueReminder]
    # Outcomes after actual send attempts
    sent: list[DueReminder] = dataclasses.field(default_factory=list)
    failed: list[DueReminder] = dataclasses.field(default_factory=list)
    dead_lettered: list[DueReminder] = dataclasses.field(default_factory=list)


@dataclasses.dataclass
class ProcessorTickResult:
    """Aggregate result of one full processor tick across all due users."""

    now: datetime
    config: ReminderConfig
    users_checked: int
    total_due: int             # sum of engine_result.total_due across users
    total_quiet_blocked: int   # sum of quiet_hours_blocked across users
    total_dispatchable: int    # reminders that would actually be sent
    total_retry_deferred: int  # reminders held back by backoff gate
    per_user: list[UserTickResult]
    total_sent: int = 0
    total_failed: int = 0
    total_dead_lettered: int = 0


# ── Public API ────────────────────────────────────────────────────────────────


async def process_tick(
    session: AsyncSession,
    now: datetime,
    config: Optional[ReminderConfig] = None,
) -> ProcessorTickResult:
    """Run one processor tick: scan all users with due reminders, send via Telegram.

    Steps:
      1. Fetch distinct user_ids that have pending reminders with scheduled_for <= now
      2. For each user (up to MAX_USERS_PER_TICK):
         a. Call dry_run_preview() from reminder_engine
         b. Apply retry-backoff gate to the would_send list
         c. Fetch user's telegram_id
         d. Send each dispatchable reminder; persist result via mark_sent /
            mark_failed / mark_dead_letter
      3. Return aggregate ProcessorTickResult

    Args:
        session: Async SQLAlchemy session.
        now:     Reference timestamp for the tick (injected for testability).
        config:  Anti-spam / quiet-hours config; defaults to ReminderConfig().

    Returns:
        ProcessorTickResult summarising what was dispatched.
    """
    if config is None:
        config = ReminderConfig()

    user_ids = await _fetch_users_with_due_reminders(session, now)

    per_user: list[UserTickResult] = []
    for user_id in user_ids:
        engine_result = await dry_run_preview(session, user_id, now, config)

        dispatchable: list[DueReminder] = []
        retry_deferred: list[DueReminder] = []

        for reminder in engine_result.would_send:
            if _is_retry_deferred(reminder, now):
                retry_deferred.append(reminder)
            else:
                dispatchable.append(reminder)

        sent: list[DueReminder] = []
        failed: list[DueReminder] = []
        dead_lettered: list[DueReminder] = []

        telegram_id = await _get_user_telegram_id(session, user_id)

        for reminder in dispatchable:
            # No telegram_id means the user row is gone — dead-letter immediately.
            if telegram_id is None:
                if reminder.id is not None:
                    await mark_dead_letter(session, reminder.id)
                dead_lettered.append(reminder)
                continue

            ok = await send_telegram(telegram_id, reminder.message)
            if ok:
                if reminder.id is not None:
                    await mark_sent(session, reminder.id, now)
                sent.append(reminder)
            else:
                if reminder.id is not None:
                    if reminder.retry_attempt + 1 >= MAX_ATTEMPTS:
                        await mark_dead_letter(session, reminder.id)
                        dead_lettered.append(reminder)
                    else:
                        await mark_failed(session, reminder.id, now, reminder.retry_attempt)
                        failed.append(reminder)
                else:
                    failed.append(reminder)

        per_user.append(
            UserTickResult(
                user_id=user_id,
                engine_result=engine_result,
                dispatchable=dispatchable,
                retry_deferred=retry_deferred,
                sent=sent,
                failed=failed,
                dead_lettered=dead_lettered,
            )
        )

    return ProcessorTickResult(
        now=now,
        config=config,
        users_checked=len(per_user),
        total_due=sum(u.engine_result.total_due for u in per_user),
        total_quiet_blocked=sum(u.engine_result.quiet_hours_blocked for u in per_user),
        total_dispatchable=sum(len(u.dispatchable) for u in per_user),
        total_retry_deferred=sum(len(u.retry_deferred) for u in per_user),
        per_user=per_user,
        total_sent=sum(len(u.sent) for u in per_user),
        total_failed=sum(len(u.failed) for u in per_user),
        total_dead_lettered=sum(len(u.dead_lettered) for u in per_user),
    )


# ── Internal helpers ──────────────────────────────────────────────────────────


async def _get_user_telegram_id(
    session: AsyncSession,
    user_id: int,
) -> Optional[int]:
    """Return telegram_id for the given internal user_id, or None if not found."""
    result = await session.execute(
        select(User.telegram_id).where(User.id == user_id)
    )
    return result.scalar_one_or_none()


async def _fetch_users_with_due_reminders(
    session: AsyncSession,
    now: datetime,
) -> list[int]:
    """Return distinct user_ids with at least one pending reminder due by *now*.

    Capped at MAX_USERS_PER_TICK to bound a single tick's work.
    Phase 5c may extend this with priority ordering (high-priority users first).
    """
    result = await session.execute(
        select(distinct(ScheduledReminder.user_id))
        .where(
            ScheduledReminder.status == "pending",
            ScheduledReminder.scheduled_for <= now,
        )
        .limit(MAX_USERS_PER_TICK)
    )
    return list(result.scalars().all())


def _is_retry_deferred(reminder: DueReminder, now: datetime) -> bool:
    """Return True if this reminder should be held back by the retry backoff policy.

    Scaffold logic: uses retry_attempt already stored on the DueReminder.
    The ScheduledReminder model does not yet carry retry_count / next_retry_at
    columns (Phase 5c concern). Here we model the *decision* only:

    - attempt 0 (first delivery): never deferred by this gate
    - attempt >= 1: compute simulated next_retry_at from scheduled_for + backoff
      If simulated next_retry_at > now → deferred

    In Phase 5c, reminder.retry_attempt will be read from the DB row, and
    next_retry_at will be a persisted column rather than a simulation.
    """
    if reminder.retry_attempt == 0:
        return False  # first-time delivery: never deferred

    delay = retry_delay_minutes(reminder.retry_attempt)
    if delay is None:
        # Exceeded MAX_ATTEMPTS — mark as deferred (Phase 5c will dead-letter these)
        return True

    simulated_next_retry_at = reminder.scheduled_for + timedelta(minutes=delay)
    return simulated_next_retry_at > now


def next_retry_at(reminder: DueReminder) -> Optional[datetime]:
    """Compute the wall-clock time for the next retry attempt.

    Returns None when MAX_ATTEMPTS is reached (no further retries).
    Scaffolding utility; Phase 5c will persist this on the DB row.
    """
    delay = retry_delay_minutes(reminder.retry_attempt + 1)
    if delay is None:
        return None
    return reminder.scheduled_for + timedelta(minutes=delay)
