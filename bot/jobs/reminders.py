"""Phase 4: Proactive reminder engine — calendar, overdue tasks, routines, nudges."""
import logging
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.connection import get_session
from bot.database.models import (
    CalendarEvent, Routine, RoutineCompletion,
    ScheduledReminder, Task, User,
)
from bot.telegram.sender import send_message

logger = logging.getLogger(__name__)


async def process_reminders() -> None:
    """
    Runs every 30 minutes.
    Sends proactive reminders: calendar events, overdue tasks, evening routine check, stale nudges.
    Uses ScheduledReminder table to track sent reminders and avoid duplicates.
    """
    now_berlin = datetime.now(tz=ZoneInfo("Europe/Berlin"))
    today = now_berlin.date()
    today_start = datetime.combine(today, datetime.min.time())

    async with get_session() as session:
        result = await session.execute(
            select(User).where(User.is_active == True)  # noqa: E712
        )
        users = result.scalars().all()

        for user in users:
            s = user.settings or {}
            if not s.get("proactive_enabled", True):
                continue

            try:
                # 1. Calendar event reminders (run every time)
                await _check_calendar_reminders(session, user, now_berlin, today_start)

                # 2. Due-today task push with inline buttons (09:00–16:00)
                if 9 <= now_berlin.hour < 16:
                    await _check_due_today_tasks(session, user, today, today_start)

                # 3. Overdue task summary (once per day after 8:00)
                if now_berlin.hour >= 8:
                    await _check_overdue_tasks(session, user, today, today_start)

                # 4. Midday routine reminder (once per day 11:30–13:30)
                if 11 <= now_berlin.hour < 14:
                    await _check_midday_routine_reminders(session, user, today, today_start)

                # 5. Evening routine reminder (once per day after 18:00)
                if now_berlin.hour >= 18:
                    await _check_routine_reminders(session, user, today, today_start)

                # 6. Stale task/objective nudge (once per day after 10:00)
                if now_berlin.hour >= 10:
                    await _check_stale_nudges(session, user, today, today_start)

                # 7. Commitment due reminders (once per day at 09:00)
                if now_berlin.hour == 9:
                    await _check_commitment_reminders(session, user, today, today_start)

            except Exception:
                logger.exception("Error processing reminders for user %s", user.id)


async def _check_calendar_reminders(
    session: AsyncSession, user: User, now_berlin: datetime, today_start: datetime
) -> None:
    """Send reminder for calendar events starting in the next 30–90 minutes."""
    now_utc = now_berlin.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)
    window_start = now_utc + timedelta(minutes=30)
    window_end = now_utc + timedelta(minutes=90)

    result = await session.execute(
        select(CalendarEvent).where(and_(
            CalendarEvent.user_id == user.id,
            CalendarEvent.start_time >= window_start,
            CalendarEvent.start_time <= window_end,
        ))
    )
    events = result.scalars().all()

    for event in events:
        reminder_type = f"cal_{event.id}"[:30]
        if await _already_reminded(session, user.id, reminder_type, today_start):
            continue

        delta = event.start_time - now_utc
        minutes = int(delta.total_seconds() / 60)
        msg = f"⏰ In {minutes} Minuten: *{event.title}*"
        if event.event_type == "training":
            msg += "\n💪 Zeit für dein Training!"
        elif event.event_type == "meeting":
            msg += "\n📞 Bereite dich auf dein Meeting vor."
        elif event.event_type == "deadline":
            msg += "\n⚠️ Deadline heute!"

        await send_message(user.telegram_id, msg)
        await _mark_reminder(session, user.id, reminder_type, msg)
        logger.info("Calendar reminder sent to user %s for event %s", user.id, event.id)


async def _check_due_today_tasks(
    session: AsyncSession, user: User, today: date, today_start: datetime
) -> None:
    """Send push reminders for tasks due today — with inline ✅/⏭ buttons."""
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    from bot.telegram.sender import get_bot

    if await _already_reminded(session, user.id, "due_today", today_start):
        return

    result = await session.execute(
        select(Task).where(and_(
            Task.user_id == user.id,
            Task.status.in_(["todo", "in_progress"]),
            Task.due_date == today,
            Task.category != "shopping",
        )).order_by(Task.priority.asc()).limit(5)
    )
    due_today = result.scalars().all()

    if not due_today:
        return

    bot = get_bot()
    sent = 0
    for task in due_today[:3]:  # max 3 inline pushes
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Erledigt", callback_data=f"next_done_{task.id}"),
            InlineKeyboardButton("⏭ Verschieben", callback_data=f"next_skip_{task.id}"),
        ]])
        msg = (
            f"📌 *Heute fällig:*\n"
            f"{task.title}\n"
            f"_Priorität {task.priority} · {'→ Ziel verknüpft' if task.objective_id else 'kein Ziel'}_"
        )
        try:
            await bot.send_message(
                chat_id=user.telegram_id,
                text=msg,
                parse_mode="Markdown",
                reply_markup=keyboard,
            )
            sent += 1
        except Exception:
            logger.exception("Due-today push failed for task %s user %s", task.id, user.id)

    if sent:
        remaining = len(due_today) - sent
        if remaining > 0:
            extra_msg = f"📋 +{remaining} weitere Tasks heute fällig — nutze /next für die vollständige Liste."
            await send_message(user.telegram_id, extra_msg)
        await _mark_reminder(session, user.id, "due_today", f"{sent} due-today tasks pushed")
        logger.info("Due-today push sent to user %s (%d tasks)", user.id, sent)


async def _check_overdue_tasks(
    session: AsyncSession, user: User, today: date, today_start: datetime
) -> None:
    """Send daily overdue task summary."""
    if await _already_reminded(session, user.id, "overdue_tasks", today_start):
        return

    result = await session.execute(
        select(Task).where(and_(
            Task.user_id == user.id,
            Task.status.in_(["todo", "in_progress"]),
            Task.due_date < today,
            Task.category != "shopping",
        )).order_by(Task.priority.asc()).limit(5)
    )
    overdue = result.scalars().all()

    if not overdue:
        return

    tasks_str = "\n".join(f"  ⚠️ {t.title} (fällig: {t.due_date})" for t in overdue[:5])
    extra = f"\n... und {len(overdue) - 5} weitere" if len(overdue) > 5 else ""
    msg = f"📋 *{len(overdue)} überfällige Tasks:*\n{tasks_str}{extra}\n\nWann erledigst du sie?"

    await send_message(user.telegram_id, msg)
    await _mark_reminder(session, user.id, "overdue_tasks", msg)
    logger.info("Overdue task reminder sent to user %s", user.id)


async def _check_midday_routine_reminders(
    session: AsyncSession, user: User, today: date, today_start: datetime
) -> None:
    """Send midday reminder for incomplete midday routines."""
    if await _already_reminded(session, user.id, "routine_midday", today_start):
        return

    routine_result = await session.execute(
        select(Routine).where(and_(
            Routine.user_id == user.id,
            Routine.status == "active",
            Routine.time_of_day == "midday",
        ))
    )
    routines = routine_result.scalars().all()

    if not routines:
        return

    comp_result = await session.execute(
        select(RoutineCompletion.routine_id).where(and_(
            RoutineCompletion.user_id == user.id,
            RoutineCompletion.completed_at >= today_start,
        ))
    )
    done_ids = set(comp_result.scalars().all())
    pending = [r for r in routines if r.id not in done_ids]

    if not pending:
        return

    routines_str = "\n".join(f"  ☐ {r.title}" for r in pending[:5])
    msg = f"☀️ *Mittags-Routinen:*\n{routines_str}\n\nKurze Mittagspause nutzen!"

    await send_message(user.telegram_id, msg)
    await _mark_reminder(session, user.id, "routine_midday", msg)
    logger.info("Routine midday reminder sent to user %s", user.id)


async def _check_routine_reminders(
    session: AsyncSession, user: User, today: date, today_start: datetime
) -> None:
    """Send evening reminder for incomplete evening/anytime routines."""
    if await _already_reminded(session, user.id, "routine_evening", today_start):
        return

    routine_result = await session.execute(
        select(Routine).where(and_(
            Routine.user_id == user.id,
            Routine.status == "active",
            Routine.time_of_day.in_(["evening", "anytime"]),
        ))
    )
    routines = routine_result.scalars().all()

    if not routines:
        return

    comp_result = await session.execute(
        select(RoutineCompletion.routine_id).where(and_(
            RoutineCompletion.user_id == user.id,
            RoutineCompletion.completed_at >= today_start,
        ))
    )
    done_ids = set(comp_result.scalars().all())
    pending = [r for r in routines if r.id not in done_ids]

    if not pending:
        return

    routines_str = "\n".join(f"  ☐ {r.title}" for r in pending[:5])
    msg = f"🌙 *Abend-Routinen noch offen:*\n{routines_str}\n\nNoch Zeit heute Abend!"

    await send_message(user.telegram_id, msg)
    await _mark_reminder(session, user.id, "routine_evening", msg)
    logger.info("Routine evening reminder sent to user %s", user.id)


async def _check_stale_nudges(
    session: AsyncSession, user: User, today: date, today_start: datetime
) -> None:
    """Send a gentle nudge for tasks with no progress for >3 days."""
    if await _already_reminded(session, user.id, "stale_nudge", today_start):
        return

    three_days_ago = datetime.combine(today - timedelta(days=3), datetime.min.time())

    result = await session.execute(
        select(Task).where(and_(
            Task.user_id == user.id,
            Task.status.in_(["todo", "in_progress"]),
            Task.category != "shopping",
            Task.updated_at <= three_days_ago,
        )).order_by(Task.priority.asc()).limit(3)
    )
    stale = result.scalars().all()

    if not stale:
        # Try created_at as fallback for tasks without updated_at
        result2 = await session.execute(
            select(Task).where(and_(
                Task.user_id == user.id,
                Task.status.in_(["todo", "in_progress"]),
                Task.category != "shopping",
                Task.updated_at == None,  # noqa: E711
                Task.created_at <= three_days_ago,
            )).order_by(Task.priority.asc()).limit(1)
        )
        stale = result2.scalars().all()

    if not stale:
        return

    task = stale[0]
    ref_date = task.updated_at or task.created_at
    days_stale = (today - ref_date.date()).days if ref_date else 3
    msg = (
        f"💭 *Sanfter Nudge:*\n"
        f'„{task.title}" wartet seit {days_stale} Tagen auf Fortschritt.\n\n'
        f"Noch aktuell? Soll ich das erledigt markieren oder hast du Zeit heute?"
    )

    await send_message(user.telegram_id, msg)
    await _mark_reminder(session, user.id, "stale_nudge", msg)
    logger.info("Stale nudge sent to user %s for task %s", user.id, task.id)


async def _already_reminded(
    session: AsyncSession, user_id: int, reminder_type: str, today_start: datetime
) -> bool:
    """Check if this reminder type was already sent today."""
    result = await session.execute(
        select(ScheduledReminder).where(and_(
            ScheduledReminder.user_id == user_id,
            ScheduledReminder.reminder_type == reminder_type,
            ScheduledReminder.status == "sent",
            ScheduledReminder.sent_at >= today_start,
        ))
    )
    return result.scalar_one_or_none() is not None


async def _mark_reminder(
    session: AsyncSession, user_id: int, reminder_type: str, message: str
) -> None:
    """Record a sent reminder to prevent duplicates. Also sends web push."""
    now = datetime.utcnow()
    reminder = ScheduledReminder(
        user_id=user_id,
        reminder_type=reminder_type,
        message=message[:500],
        scheduled_for=now,
        status="sent",
        sent_at=now,
        auto_generated=True,
    )
    session.add(reminder)
    await session.flush()

    # Dual delivery: also send via web push if subscribed
    try:
        from bot.core.push import send_push_if_subscribed
        # Strip markdown for push notification body
        clean = message.replace("*", "").replace("_", "")[:200]
        await send_push_if_subscribed(
            session, user_id, title="Personal OS", body=clean, tag=reminder_type,
        )
    except Exception:
        logger.debug("Web push failed (non-fatal) for reminder %s", reminder_type)


async def _check_commitment_reminders(
    session: AsyncSession, user: User, today: date, today_start: datetime
) -> None:
    """Send reminder for commitments due today or tomorrow."""
    from bot.database.models import Commitment
    tomorrow = today + timedelta(days=1)

    result = await session.execute(
        select(Commitment).where(
            and_(
                Commitment.user_id == user.id,
                Commitment.status.in_(["pending", "overdue"]),
                Commitment.due_date <= tomorrow,
            )
        )
    )
    commitments = result.scalars().all()

    if not commitments:
        return

    reminder_type = f"commitments_{today}"
    if await _already_reminded(session, user.id, reminder_type, today_start):
        return

    lines = ["📋 *Offene Zusagen:*"]
    for c in commitments:
        due_info = ""
        if c.due_date == today:
            due_info = " ⚠️ *HEUTE fällig*"
        elif c.due_date and c.due_date < today:
            due_info = " ❗ *ÜBERFÄLLIG*"
        elif c.due_date == tomorrow:
            due_info = " → morgen fällig"
        lines.append(f"• {c.description}{due_info}")

    msg = "\n".join(lines)
    await send_message(user.telegram_id, msg)
    await _mark_reminded(session, user.id, reminder_type, msg)


# Legacy stubs — kept for import compatibility
async def send_routine_reminders() -> None:
    """Replaced by process_reminders() in Phase 4."""
    logger.info("send_routine_reminders: use process_reminders() instead")


# Alias for backward-compatible imports
check_proactive_reminders = process_reminders
