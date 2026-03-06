"""CORE-5b: Due reminder processor loop scaffold (read-only / safe mode).

Responsibilities:
- Fetch all distinct user IDs that have pending reminders due at *now*
- For each user: delegate per-user batching + quiet-hours gate to reminder_engine
- Apply retry backoff policy: mark items whose simulated next_retry_at > now as
  deferred (no DB column yet; scaffold models the decision only)
- Produce a ProcessorTickResult summary per tick

No DB rows are mutated. No Telegram messages are sent.
Phase 5c will wire:
  - Actual Telegram send call
  - mark_sent() on success
  - Persist retry_count + next_retry_at on ScheduledReminder rows on failure
"""

from __future__ import annotations

import dataclasses
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import distinct, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.core.reminder_engine import (
    BATCH_SIZE,
    DueReminder,
    EnginePreviewResult,
    dry_run_preview,
    retry_delay_minutes,
)
from bot.core.reminder_factory import ReminderConfig
from bot.database.models import ScheduledReminder


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


# ── Public API ────────────────────────────────────────────────────────────────


async def process_tick(
    session: AsyncSession,
    now: datetime,
    config: Optional[ReminderConfig] = None,
) -> ProcessorTickResult:
    """Run one processor tick: scan all users with due reminders, apply policy.

    Pure read-only — no DB writes, no external sends.

    Steps:
      1. Fetch distinct user_ids that have pending reminders with scheduled_for <= now
      2. For each user (up to MAX_USERS_PER_TICK):
         a. Call dry_run_preview() from reminder_engine
         b. Apply retry-backoff gate to the would_send list
         c. Collect UserTickResult
      3. Return aggregate ProcessorTickResult

    Args:
        session: Async SQLAlchemy session (read-only usage).
        now:     Reference timestamp for the tick (injected for testability).
        config:  Anti-spam / quiet-hours config; defaults to ReminderConfig().

    Returns:
        ProcessorTickResult summarising what would be dispatched.
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

        per_user.append(
            UserTickResult(
                user_id=user_id,
                engine_result=engine_result,
                dispatchable=dispatchable,
                retry_deferred=retry_deferred,
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
    )


# ── Internal helpers ──────────────────────────────────────────────────────────


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
