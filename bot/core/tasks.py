"""CRUD for Tasks — including shopping category and next-action support."""
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
    objective_id: Optional[int] = None,
    parent_task_id: Optional[int] = None,
    blocked_by_task_id: Optional[int] = None,
    priority: int = 3,
    category: str = "general",
    due_date: Optional[str] = None,
) -> Task:
    """Create a new Task. Use category='shopping' for shopping items."""
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
        objective_id=objective_id,
        parent_task_id=parent_task_id,
        blocked_by_task_id=blocked_by_task_id,
        priority=priority,
        category=category,
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


async def find_open_tasks_by_query(
    session: AsyncSession, user_id: int, query: str, limit: int = 5,
) -> list[Task]:
    """V3 — fuzzy title match for natural-language completion.

    'anzughose gereinigt' → matches Task 'Anzughose zur Reinigung bringen'.
    Tokenizes the query, requires ≥1 token (≥3 chars) to match the title.
    """
    tokens = [t.strip().lower() for t in query.split() if len(t.strip()) >= 3]
    if not tokens:
        return []
    candidates = (await session.execute(
        select(Task).where(and_(
            Task.user_id == user_id,
            Task.status.in_(["todo", "in_progress"]),
        )).order_by(Task.priority.asc()).limit(200)
    )).scalars().all()

    scored: list[tuple[int, Task]] = []
    for t in candidates:
        title_lower = (t.title or "").lower()
        score = sum(1 for tok in tokens if tok in title_lower)
        if score > 0:
            scored.append((score, t))
    scored.sort(key=lambda x: (-x[0], x.id if False else 0))
    return [t for _, t in scored[:limit]]


async def find_and_complete_task(
    session: AsyncSession, user_id: int, query: str,
) -> dict:
    """V3 — smart-match completion. Returns:
        {"matched": Task, "task": Task} on success (1 strong hit)
        {"ambiguous": [Task, ...]}        on multiple hits
        {"not_found": True}               on no match
    """
    hits = await find_open_tasks_by_query(session, user_id, query)
    if not hits:
        return {"not_found": True, "query": query}
    if len(hits) == 1:
        task = await complete_task(session, user_id, hits[0].id)
        return {"completed": True, "task": task}
    # Multiple — return the list so AI can ask user which
    return {
        "ambiguous": True,
        "matches": [
            {"id": t.id, "title": t.title, "category": t.category} for t in hits
        ],
    }


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
    """Get open tasks ordered by priority (1=highest) then due date."""
    result = await session.execute(
        select(Task)
        .where(and_(
            Task.user_id == user_id,
            Task.status.in_(["todo", "in_progress"]),
            Task.category != "shopping",
        ))
        .order_by(Task.priority.asc(), Task.due_date.asc().nulls_last())
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_prioritized_tasks(session: AsyncSession, user_id: int, limit: int = 5) -> list[Task]:
    """Get top tasks by priority (1=highest), due date, then creation date."""
    result = await session.execute(
        select(Task)
        .where(and_(
            Task.user_id == user_id,
            Task.status.in_(["todo", "in_progress"]),
            Task.category != "shopping",
        ))
        .order_by(Task.priority.asc(), Task.due_date.asc().nulls_last(), Task.created_at.asc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_open_shopping_items(session: AsyncSession, user_id: int) -> list[Task]:
    """Get open shopping tasks."""
    result = await session.execute(
        select(Task)
        .where(and_(
            Task.user_id == user_id,
            Task.category == "shopping",
            Task.status == "todo",
        ))
        .order_by(Task.created_at.asc())
    )
    return list(result.scalars().all())


async def get_next_task_in_kr(session: AsyncSession, kr_id: int) -> Optional[Task]:
    """Get the next todo task in the same key result (for next-action principle)."""
    result = await session.execute(
        select(Task)
        .where(and_(
            Task.key_result_id == kr_id,
            Task.status == "todo",
        ))
        .order_by(Task.priority.asc(), Task.created_at.asc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def update_task(
    session: AsyncSession,
    task_id: int,
    user_id: int,
    **kwargs,
) -> Optional[Task]:
    """Update task fields."""
    result = await session.execute(
        select(Task).where(and_(Task.id == task_id, Task.user_id == user_id))
    )
    task = result.scalar_one_or_none()
    if task:
        for key, value in kwargs.items():
            setattr(task, key, value)
        await session.flush()
    return task


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
