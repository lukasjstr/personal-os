"""V3 P07 — Reminder severity + escalation state machine.

Severity classification (`determine_severity`) — pure function, no DB:
  - critical: linked task due today, linked KR streak broken (24h),
              linked calendar event in next 30 min, linked routine missed 3+d
  - important: linked to active KR/routine/objective
  - normal:   everything else

Escalation pass (`run_escalation_sweep`) — called by the reminders job every
30 min. For each sent important/critical reminder whose escalation window has
elapsed, check whether the user acknowledged (completed the linked task,
completed the linked routine today, or replied via Telegram since sent_at).
If not, advance escalation_step and either send a sharp nudge (step 1) or
flag for the next morning brief (step ≥2). Step 3+ stops sending — the
morning brief Festnagel handles it from then on.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import (
    CalendarEvent,
    Conversation,
    KeyResult,
    Log,
    Objective,
    Routine,
    RoutineCompletion,
    ScheduledReminder,
    Task,
    User,
)

logger = logging.getLogger(__name__)


CRITICAL_TYPES: frozenset[str] = frozenset({
    "task_deadline", "streak_warning", "calendar_prep",
})

# Hours to wait after sending before checking acknowledgement
ESCALATION_WINDOW_HOURS: dict[str, int] = {
    "critical": 2,
    "important": 4,
    "normal": 0,  # no escalation
}


# ─── Severity classification ─────────────────────────────────────────────────


async def determine_severity(
    session: AsyncSession,
    user_id: int,
    *,
    linked_task_id: Optional[int] = None,
    linked_kr_id: Optional[int] = None,
    linked_routine_id: Optional[int] = None,
    linked_event_id: Optional[int] = None,
    today: Optional[date] = None,
) -> str:
    """Return 'critical' | 'important' | 'normal'.

    Critical conditions (any one triggers):
        - Task due today
        - KR streak broken in last 24h (no logs but >2 weekly target)
        - Calendar event starts within next 30 minutes
        - Routine missed 3+ consecutive scheduled days
    Important conditions:
        - Linked to an active task/KR/routine that isn't critical
    Else: normal.
    """
    if today is None:
        today = date.today()

    # ── Critical: task due today ─────────────────────────────────────────────
    if linked_task_id is not None:
        task = await session.get(Task, linked_task_id)
        if task is not None and task.due_date == today and task.status != "done":
            return "critical"

    # ── Critical: calendar event in next 30 minutes ──────────────────────────
    if linked_event_id is not None:
        ev = await session.get(CalendarEvent, linked_event_id)
        if ev is not None:
            now = datetime.utcnow()
            delta = (ev.start_time - now).total_seconds() / 60
            if 0 <= delta <= 30:
                return "critical"

    # ── Critical: KR streak broken (≥7 days since last log, target>0) ──────
    if linked_kr_id is not None:
        kr = await session.get(KeyResult, linked_kr_id)
        if kr is not None and kr.target_value and kr.target_value > 0:
            last = (await session.execute(
                select(Log).where(and_(
                    Log.user_id == user_id,
                    Log.key_result_id == linked_kr_id,
                )).order_by(Log.logged_at.desc()).limit(1)
            )).scalar_one_or_none()
            if last is None or (datetime.utcnow() - last.logged_at) >= timedelta(days=7):
                return "critical"

    # ── Critical: routine missed 3+ scheduled days ───────────────────────────
    if linked_routine_id is not None:
        routine = await session.get(Routine, linked_routine_id)
        if routine is not None:
            since = datetime.utcnow() - timedelta(days=3)
            last_completion = (await session.execute(
                select(RoutineCompletion).where(and_(
                    RoutineCompletion.user_id == user_id,
                    RoutineCompletion.routine_id == linked_routine_id,
                )).order_by(RoutineCompletion.completed_at.desc()).limit(1)
            )).scalar_one_or_none()
            if last_completion is None or last_completion.completed_at <= since:
                return "critical"

    # ── Important: anything linked at all ────────────────────────────────────
    if any(x is not None for x in (linked_task_id, linked_kr_id, linked_routine_id)):
        return "important"

    return "normal"


# ─── Acknowledgement check ───────────────────────────────────────────────────


async def is_acknowledged(
    session: AsyncSession, reminder: ScheduledReminder
) -> bool:
    """True if the user acted on this reminder since it was sent.

    Acknowledged via:
      - linked Task is now done
      - linked Routine has a completion since sent_at
      - any user-side conversation entry exists since sent_at
    """
    if reminder.sent_at is None:
        return False

    sent_at = reminder.sent_at

    if reminder.linked_task_id is not None:
        task = await session.get(Task, reminder.linked_task_id)
        if task is not None and task.status == "done":
            if task.completed_at is None or task.completed_at >= sent_at:
                return True

    if reminder.linked_routine_id is not None:
        comp = (await session.execute(
            select(RoutineCompletion).where(and_(
                RoutineCompletion.user_id == reminder.user_id,
                RoutineCompletion.routine_id == reminder.linked_routine_id,
                RoutineCompletion.completed_at >= sent_at,
            )).limit(1)
        )).scalar_one_or_none()
        if comp is not None:
            return True

    # Any user message since the reminder counts as a basic ack
    last_user_msg = (await session.execute(
        select(Conversation).where(and_(
            Conversation.user_id == reminder.user_id,
            Conversation.role == "user",
            Conversation.created_at >= sent_at,
        )).limit(1)
    )).scalar_one_or_none()
    return last_user_msg is not None


# ─── Escalation sweep ────────────────────────────────────────────────────────


async def run_escalation_sweep(session: AsyncSession) -> dict:
    """Walk recently-sent important/critical reminders and escalate the ignored ones.

    Returns a counters dict for logging/test inspection:
      {"checked": N, "step_1": N, "step_2_flagged": N, "step_3_stop": N}
    """
    now = datetime.utcnow()
    counters = {"checked": 0, "step_1": 0, "step_2_flagged": 0, "step_3_stop": 0}

    # Look at reminders sent in the last 48h that are important/critical and
    # have step < 3 (still escalatable).
    window_start = now - timedelta(hours=48)
    rows = (await session.execute(
        select(ScheduledReminder).where(and_(
            ScheduledReminder.status == "sent",
            ScheduledReminder.sent_at >= window_start,
            ScheduledReminder.severity.in_(["important", "critical"]),
            ScheduledReminder.escalation_step < 3,
        ))
    )).scalars().all()

    for r in rows:
        counters["checked"] += 1
        wait_hours = ESCALATION_WINDOW_HOURS.get(r.severity, 0)
        if wait_hours == 0:
            continue
        if r.sent_at is None or (now - r.sent_at) < timedelta(hours=wait_hours):
            continue
        if await is_acknowledged(session, r):
            continue

        # Not acknowledged — escalate
        r.escalation_step = (r.escalation_step or 0) + 1
        if r.escalation_step == 1:
            await _send_step1_nudge(session, r)
            counters["step_1"] += 1
        elif r.escalation_step == 2:
            # Flag for tomorrow's morning brief (no extra Telegram ping)
            counters["step_2_flagged"] += 1
        else:
            # step >= 3 — stop. The morning brief Festnagel handles the rest.
            counters["step_3_stop"] += 1

    await session.commit()
    return counters


async def _send_step1_nudge(session: AsyncSession, r: ScheduledReminder) -> None:
    """Send a hard step-1 escalation nudge via Telegram."""
    from bot.telegram.sender import send_message
    user = await session.get(User, r.user_id)
    if user is None:
        return
    # Quiet-hours respected: 22:00–08:00 Berlin → skip, escalation waits.
    try:
        from zoneinfo import ZoneInfo
        from bot.core.reminder_factory import _is_in_quiet_hours, ReminderConfig
        now_berlin = datetime.now(tz=ZoneInfo("Europe/Berlin")).replace(tzinfo=None)
        if _is_in_quiet_hours(now_berlin, ReminderConfig()):
            # Roll back the increment — try again in the next sweep
            r.escalation_step = max(0, (r.escalation_step or 1) - 1)
            return
    except Exception:
        logger.exception("Quiet-hours check failed — sending escalation anyway")

    msg = f"Reminder ignoriert: {r.message[:200]}\nStatus?"
    try:
        await send_message(user.telegram_id, msg)
    except Exception:
        logger.exception("Step-1 escalation send failed for reminder %s", r.id)


# ─── Morning brief integration ───────────────────────────────────────────────


async def get_flagged_escalations(
    session: AsyncSession, user_id: int, hours: int = 24
) -> list[ScheduledReminder]:
    """Return reminders that have been escalated to step ≥2 in the last `hours`.
    Used by morning_brief to prepend a Festnagel line."""
    since = datetime.utcnow() - timedelta(hours=hours)
    return list((await session.execute(
        select(ScheduledReminder).where(and_(
            ScheduledReminder.user_id == user_id,
            ScheduledReminder.escalation_step >= 2,
            ScheduledReminder.sent_at >= since,
        )).order_by(ScheduledReminder.sent_at.desc())
    )).scalars().all())
