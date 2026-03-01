"""CRUD for Tasks and log search."""
from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import Log, Task


async def create_task(
    session: AsyncSession,
    user_id: int,
    title: str,
    description: Optional[str] = None,
    key_result_id: Optional[int] = None,
    priority: int = 3,
    due_date: Optional[str] = None,
) -> Task:
    """Create a new Task."""
    parsed_date = None
    if due_date:
        try:
            parsed_date = date.fromisoformat(due_date)
        except ValueError:
            pass

    task = Task(
        user_id=user_id,
        title=title,
        description=description,
        key_result_id=key_result_id,
        priority=priority,
        due_date=parsed_date,
        status="todo",
    )
    session.add(task)
    await session.flush()
    return task


async def complete_task(
    session: AsyncSession,
    user_id: int,
    task_id: int,
) -> Optional[Task]:
    """Mark a task as done."""
    result = await session.execute(
        select(Task).where(and_(Task.id == task_id, Task.user_id == user_id))
    )
    task = result.scalar_one_or_none()
    if task:
        task.status = "done"
        task.completed_at = datetime.utcnow()
        await session.flush()
    return task


async def update_task_status(
    session: AsyncSession,
    user_id: int,
    task_id: int,
    status: str,
) -> Optional[Task]:
    """Update a task's status."""
    result = await session.execute(
        select(Task).where(and_(Task.id == task_id, Task.user_id == user_id))
    )
    task = result.scalar_one_or_none()
    if task:
        task.status = status
        if status == "done" and not task.completed_at:
            task.completed_at = datetime.utcnow()
        await session.flush()
    return task


async def get_open_tasks(session: AsyncSession, user_id: int, limit: int = 10) -> list[Task]:
    """Get open tasks ordered by priority."""
    result = await session.execute(
        select(Task)
        .where(and_(Task.user_id == user_id, Task.status.in_(["todo", "in_progress"])))
        .order_by(Task.priority.desc(), Task.due_date.asc().nulls_last())
        .limit(limit)
    )
    return result.scalars().all()


async def search_logs(
    session: AsyncSession,
    user_id: int,
    query: str,
    log_type: Optional[str] = None,
    days_back: int = 30,
) -> str:
    """Search log entries for a user."""
    since = datetime.utcnow() - timedelta(days=days_back)
    conditions = [Log.user_id == user_id, Log.created_at >= since]
    if log_type:
        conditions.append(Log.log_type == log_type)

    result = await session.execute(
        select(Log).where(and_(*conditions)).order_by(Log.created_at.desc()).limit(20)
    )
    logs = result.scalars().all()

    q_lower = query.lower()
    matching = [
        log for log in logs
        if q_lower in str(log.data).lower() or (log.raw_input and q_lower in log.raw_input.lower())
    ]

    if not matching:
        return f"Keine Logs für '{query}' in den letzten {days_back} Tagen gefunden."

    lines = [f"Logs für '{query}' (letzte {days_back} Tage):"]
    for log in matching[:10]:
        ts = log.logged_at.strftime("%d.%m %H:%M")
        lines.append(f"  [{ts}] {log.log_type}: {log.raw_input or str(log.data)[:100]}")

    return "\n".join(lines)
