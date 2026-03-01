"""Priority calculation and today's briefing logic."""
from datetime import date, datetime

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import CalendarEvent, Routine, RoutineCompletion, Task


async def get_todays_priorities(session: AsyncSession, user_id: int) -> str:
    """Return a formatted string of today's top priorities."""
    today = date.today()
    today_start = datetime.combine(today, datetime.min.time())
    lines: list[str] = []

    # Top tasks by priority
    task_result = await session.execute(
        select(Task)
        .where(
            and_(
                Task.user_id == user_id,
                Task.status.in_(["todo", "in_progress"]),
            )
        )
        .order_by(Task.priority.desc(), Task.due_date.asc().nulls_last())
        .limit(5)
    )
    tasks = task_result.scalars().all()
    if tasks:
        lines.append("🎯 TOP PRIORITÄTEN:")
        for i, t in enumerate(tasks, 1):
            overdue = " ⚠️ ÜBERFÄLLIG" if t.due_date and t.due_date < today else ""
            lines.append(f"  {i}. [{t.priority}★] {t.title}{overdue}")
        lines.append("")

    # Today's routines
    routine_result = await session.execute(
        select(Routine).where(
            and_(Routine.user_id == user_id, Routine.status == "active")
        )
    )
    routines = routine_result.scalars().all()
    if routines:
        completed_result = await session.execute(
            select(RoutineCompletion.routine_id).where(
                and_(
                    RoutineCompletion.user_id == user_id,
                    RoutineCompletion.completed_at >= today_start,
                )
            )
        )
        completed = set(completed_result.scalars().all())
        lines.append("📋 ROUTINEN HEUTE:")
        for r in routines:
            status = "✅" if r.id in completed else "☐"
            lines.append(f"  {status} {r.title}")
        lines.append("")

    # Today's calendar events
    cal_result = await session.execute(
        select(CalendarEvent)
        .where(
            and_(
                CalendarEvent.user_id == user_id,
                CalendarEvent.start_time >= today_start,
                CalendarEvent.start_time < datetime.combine(today, datetime.max.time()),
            )
        )
        .order_by(CalendarEvent.start_time)
    )
    events = cal_result.scalars().all()
    if events:
        lines.append("📅 KALENDER HEUTE:")
        for ev in events:
            lines.append(f"  {ev.start_time.strftime('%H:%M')} {ev.title}")
        lines.append("")

    if not lines:
        return "Heute noch keine Tasks oder Routinen geplant. Soll ich dir helfen, deinen Tag zu planen?"

    return "\n".join(lines)
