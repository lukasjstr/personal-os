"""Phase 2: Scheduled reminder creation and management.
Auto-generates reminders when tasks, routines, or key results are created.
"""
from datetime import datetime
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import ScheduledReminder


async def create_auto_reminders(
    session: AsyncSession,
    user_id: int,
    source_type: str,
    source_id: int,
) -> list[ScheduledReminder]:
    """Create automatic reminders when a task/routine/key result is created.

    Phase 2: source_type is one of 'task', 'routine', 'key_result'.
    For tasks with due_date: creates reminders at 7d, 3d, 1d before.
    For water KRs: creates 3x daily water reminders.
    For routines: creates routine reminder before scheduled time.
    """
    raise NotImplementedError("Phase 2")


async def get_pending_reminders(
    session: AsyncSession,
    user_id: int,
    before: datetime,
) -> list[ScheduledReminder]:
    """Get all pending reminders for a user that are due before the given datetime.

    Phase 2: Returns reminders with status='pending' and scheduled_for <= before.
    """
    raise NotImplementedError("Phase 2")


async def mark_sent(session: AsyncSession, reminder_id: int) -> None:
    """Mark a reminder as sent.

    Phase 2: Sets status='sent' and sent_at=now().
    """
    raise NotImplementedError("Phase 2")


async def cancel_reminders(
    session: AsyncSession,
    source_type: str,
    source_id: int,
) -> int:
    """Cancel all pending reminders linked to a source (task/routine/key_result).

    Phase 2: Sets status='cancelled' for all matching reminders.
    Returns count of cancelled reminders.
    """
    raise NotImplementedError("Phase 2")


async def create_next_action_reminder(
    session: AsyncSession,
    user_id: int,
    task_id: int,
    next_task_title: str,
    delay_minutes: int = 30,
) -> ScheduledReminder:
    """Create a next-action reminder after a task is completed.

    Phase 2: Sends a nudge after delay_minutes suggesting the next task.
    """
    raise NotImplementedError("Phase 2")
