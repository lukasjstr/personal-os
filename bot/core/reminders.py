"""Smart Reminder Engine: auto-generates reminders for tasks, routines, and key results.

When a goal is executed (via proposal_execute), this module creates contextual
ScheduledReminder rows based on the type of artifact:
- Key Results: recurring reminders based on KR context (water → 3x daily, etc.)
- Tasks with due_date: deadline reminder 1 day before
- Routines: daily reminder at the routine's time_of_day
"""
import logging
import re
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import and_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import (
    KeyResult,
    Routine,
    ScheduledReminder,
    Task,
)

logger = logging.getLogger(__name__)

# ── KR title patterns → reminder strategies ──────────────────────────────────

_WATER_PATTERN = re.compile(
    r"(wasser|water|trinken|drink|hydra|flüssigkeit|liter\b.*tag|l\s*/\s*tag)",
    re.IGNORECASE,
)
_MOVEMENT_PATTERN = re.compile(
    r"(schritt|steps|bewegung|walk|spazier|laufen|cardio|schritte)",
    re.IGNORECASE,
)
_SUPPLEMENT_PATTERN = re.compile(
    r"(supplement|vitamin|kreatin|protein|omega|magnesium|zink)",
    re.IGNORECASE,
)

_ROUTINE_TIME_MAP: dict[str, str] = {
    "morning": "07:30",
    "midday": "12:00",
    "evening": "19:00",
    "anytime": "10:00",
}


async def create_auto_reminders(
    session: AsyncSession,
    user_id: int,
    source_type: str,
    source_id: int,
) -> list[ScheduledReminder]:
    """Create automatic reminders when a task/routine/key result is created.

    Dispatches to type-specific handlers based on source_type.
    Returns the list of newly created ScheduledReminder rows.
    """
    try:
        if source_type == "key_result":
            return await _reminders_for_key_result(session, user_id, source_id)
        elif source_type == "task":
            return await _reminders_for_task(session, user_id, source_id)
        elif source_type == "routine":
            return await _reminders_for_routine(session, user_id, source_id)
        else:
            logger.warning("Unknown source_type '%s' for auto-reminders", source_type)
            return []
    except Exception:
        logger.exception(
            "Failed to create auto-reminders for %s:%d user:%d (non-fatal)",
            source_type, source_id, user_id,
        )
        return []


async def get_pending_reminders(
    session: AsyncSession,
    user_id: int,
    before: datetime,
) -> list[ScheduledReminder]:
    """Get all pending reminders for a user that are due before the given datetime."""
    result = await session.execute(
        select(ScheduledReminder).where(
            and_(
                ScheduledReminder.user_id == user_id,
                ScheduledReminder.status == "pending",
                ScheduledReminder.scheduled_for <= before,
            )
        ).order_by(ScheduledReminder.scheduled_for)
    )
    return list(result.scalars().all())


async def mark_sent(session: AsyncSession, reminder_id: int) -> None:
    """Mark a reminder as sent."""
    await session.execute(
        update(ScheduledReminder)
        .where(ScheduledReminder.id == reminder_id)
        .values(status="sent", sent_at=datetime.utcnow())
    )
    await session.flush()


async def cancel_reminders(
    session: AsyncSession,
    source_type: str,
    source_id: int,
) -> int:
    """Cancel all pending reminders linked to a source (task/routine/key_result).

    Returns count of cancelled reminders.
    """
    fk_column = {
        "key_result": ScheduledReminder.linked_key_result_id,
        "task": ScheduledReminder.linked_task_id,
        "routine": ScheduledReminder.linked_routine_id,
    }.get(source_type)

    if fk_column is None:
        return 0

    result = await session.execute(
        update(ScheduledReminder)
        .where(
            and_(
                fk_column == source_id,
                ScheduledReminder.status == "pending",
            )
        )
        .values(status="cancelled")
    )
    await session.flush()
    return result.rowcount  # type: ignore[return-value]


async def create_next_action_reminder(
    session: AsyncSession,
    user_id: int,
    task_id: int,
    next_task_title: str,
    delay_minutes: int = 30,
) -> ScheduledReminder:
    """Create a next-action reminder after a task is completed."""
    now = datetime.utcnow()
    reminder = ScheduledReminder(
        user_id=user_id,
        reminder_type="next_action",
        message=f"💡 Nächster Schritt: {next_task_title}",
        scheduled_for=now + timedelta(minutes=delay_minutes),
        linked_task_id=task_id,
        status="pending",
        auto_generated=True,
    )
    session.add(reminder)
    await session.flush()
    return reminder


# ── Internal: type-specific reminder generators ──────────────────────────────


async def _reminders_for_key_result(
    session: AsyncSession,
    user_id: int,
    kr_id: int,
) -> list[ScheduledReminder]:
    """Generate recurring reminders based on KR context."""
    result = await session.execute(
        select(KeyResult).where(KeyResult.id == kr_id)
    )
    kr = result.scalar_one_or_none()
    if kr is None:
        return []

    title_lower = (kr.title or "").lower()

    # Determine reminder strategy from KR title
    if _WATER_PATTERN.search(title_lower):
        return await _create_recurring(
            session, user_id,
            reminder_type="water",
            repeat_rule="daily:09:00,13:00,17:00",
            message_template="💧 Zeit für Wasser! Denk an dein Ziel: {title}",
            kr=kr,
        )
    elif _MOVEMENT_PATTERN.search(title_lower):
        return await _create_recurring(
            session, user_id,
            reminder_type="progress_nudge",
            repeat_rule="daily:10:00,15:00",
            message_template="🚶 Bewegungs-Check: {title}",
            kr=kr,
        )
    elif _SUPPLEMENT_PATTERN.search(title_lower):
        return await _create_recurring(
            session, user_id,
            reminder_type="routine",
            repeat_rule="daily:08:00",
            message_template="💊 Supplement-Erinnerung: {title}",
            kr=kr,
        )
    else:
        # Default: 1x daily progress nudge
        return await _create_recurring(
            session, user_id,
            reminder_type="progress_nudge",
            repeat_rule="daily:09:00",
            message_template="📊 Fortschritt loggen: {title}",
            kr=kr,
        )


async def _reminders_for_task(
    session: AsyncSession,
    user_id: int,
    task_id: int,
) -> list[ScheduledReminder]:
    """Create deadline reminder 1 day before task due_date."""
    result = await session.execute(
        select(Task).where(Task.id == task_id)
    )
    task = result.scalar_one_or_none()
    if task is None or task.due_date is None:
        return []

    reminder_time = datetime.combine(
        task.due_date - timedelta(days=1),
        datetime.min.time().replace(hour=9),
    )
    # Don't create reminders in the past
    if reminder_time <= datetime.utcnow():
        return []

    reminder = ScheduledReminder(
        user_id=user_id,
        reminder_type="task_deadline",
        message=f"⏰ Morgen fällig: {task.title}",
        scheduled_for=reminder_time,
        linked_task_id=task_id,
        status="pending",
        auto_generated=True,
    )
    session.add(reminder)
    await session.flush()
    logger.info("Auto-reminder: task_deadline for task %d user %d", task_id, user_id)
    return [reminder]


async def _reminders_for_routine(
    session: AsyncSession,
    user_id: int,
    routine_id: int,
) -> list[ScheduledReminder]:
    """Create recurring reminder for a routine based on its time_of_day."""
    result = await session.execute(
        select(Routine).where(Routine.id == routine_id)
    )
    routine = result.scalar_one_or_none()
    if routine is None:
        return []

    time_str = _ROUTINE_TIME_MAP.get(routine.time_of_day or "anytime", "10:00")
    repeat_rule = f"daily:{time_str}"

    return await _create_recurring(
        session, user_id,
        reminder_type="routine",
        repeat_rule=repeat_rule,
        message_template="🔄 Routine: {title}",
        routine=routine,
    )


async def _create_recurring(
    session: AsyncSession,
    user_id: int,
    *,
    reminder_type: str,
    repeat_rule: str,
    message_template: str,
    kr: Optional[KeyResult] = None,
    routine: Optional[Routine] = None,
) -> list[ScheduledReminder]:
    """Create initial pending ScheduledReminder rows for a recurring reminder.

    Parses the repeat_rule to determine today's remaining times and creates
    pending rows for them. The expander job will create future occurrences.
    """
    from bot.core.reminder_expander import parse_repeat_rule

    title = ""
    linked_kr_id = None
    linked_routine_id = None

    if kr is not None:
        title = kr.title or ""
        linked_kr_id = kr.id
    elif routine is not None:
        title = routine.title or ""
        linked_routine_id = routine.id

    message = message_template.format(title=title)
    frequency, times, weekday = parse_repeat_rule(repeat_rule)

    now = datetime.utcnow()
    today = now.date()
    created: list[ScheduledReminder] = []

    for time_str in times:
        try:
            h, m = (int(x) for x in time_str.split(":")[:2])
        except (ValueError, IndexError):
            continue

        scheduled_for = datetime(today.year, today.month, today.day, h, m)
        # If time already passed today, schedule for tomorrow
        if scheduled_for <= now:
            scheduled_for += timedelta(days=1)

        reminder = ScheduledReminder(
            user_id=user_id,
            reminder_type=reminder_type,
            message=message,
            scheduled_for=scheduled_for,
            repeat_rule=repeat_rule,
            linked_key_result_id=linked_kr_id,
            linked_routine_id=linked_routine_id,
            status="pending",
            auto_generated=True,
        )
        session.add(reminder)
        await session.flush()
        created.append(reminder)

    if created:
        logger.info(
            "Auto-reminder: %d %s reminders (rule=%s) for user %d",
            len(created), reminder_type, repeat_rule, user_id,
        )
    return created


# Legacy stubs — kept for import compatibility
async def send_routine_reminders() -> None:
    """Replaced by process_reminders() in Phase 4."""
    logger.info("send_routine_reminders: use process_reminders() instead")
