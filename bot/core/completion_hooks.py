"""CORE-7 completion hooks — KR/objective progress updates + next-action surfacing."""
from typing import Optional

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.core.explainability import get_task_reason
from bot.database.models import KeyResult, Objective, Routine, Task


async def update_kr_on_task_complete(
    session: AsyncSession,
    task: Task,
) -> Optional[KeyResult]:
    """Increment KR current_value when a linked task is completed.

    Strategy per metric_type:
    - checklist / number: +1
    - boolean: set to 1.0 (done)
    - percentage: recalculate from done/total tasks on this KR
    - streak: no-op (streaks driven by routine completions)
    """
    if not task.key_result_id:
        return None

    result = await session.execute(
        select(KeyResult).where(KeyResult.id == task.key_result_id)
    )
    kr = result.scalar_one_or_none()
    if not kr or kr.status != "active":
        return None

    if kr.metric_type in ("checklist", "number"):
        kr.current_value = (kr.current_value or 0.0) + 1.0
    elif kr.metric_type == "boolean":
        kr.current_value = 1.0
    elif kr.metric_type == "percentage":
        total_res = await session.execute(
            select(func.count()).select_from(Task).where(Task.key_result_id == kr.id)
        )
        done_res = await session.execute(
            select(func.count()).select_from(Task).where(
                and_(Task.key_result_id == kr.id, Task.status == "done")
            )
        )
        total = total_res.scalar() or 1
        done = done_res.scalar() or 0
        kr.current_value = round((done / total) * 100.0, 1)
    # streak: driven by routine completions, skip here

    if kr.target_value and kr.current_value >= kr.target_value and kr.status == "active":
        kr.status = "completed"

    await session.flush()
    return kr


async def update_kr_on_routine_complete(
    session: AsyncSession,
    routine: Routine,
) -> Optional[KeyResult]:
    """Increment KR current_value when a linked routine is completed.

    Applies to all metric_types that a routine might drive (streak, number, checklist).
    """
    if not routine.linked_key_result_id:
        return None

    result = await session.execute(
        select(KeyResult).where(KeyResult.id == routine.linked_key_result_id)
    )
    kr = result.scalar_one_or_none()
    if not kr or kr.status != "active":
        return None

    kr.current_value = (kr.current_value or 0.0) + 1.0

    if kr.target_value and kr.current_value >= kr.target_value and kr.status == "active":
        kr.status = "completed"

    await session.flush()
    return kr


async def check_objective_auto_complete(
    session: AsyncSession,
    objective_id: int,
) -> bool:
    """Mark objective completed if all its active KRs have reached their target.

    Returns True if the objective was just completed, False otherwise.
    """
    obj_res = await session.execute(
        select(Objective).where(Objective.id == objective_id)
    )
    obj = obj_res.scalar_one_or_none()
    if not obj or obj.status != "active":
        return False

    kr_res = await session.execute(
        select(KeyResult).where(
            and_(KeyResult.objective_id == objective_id, KeyResult.status.in_(["active", "completed"]))
        )
    )
    krs = kr_res.scalars().all()
    if not krs:
        return False

    all_done = all(
        kr.status == "completed"
        or (kr.target_value is not None and kr.current_value >= kr.target_value)
        for kr in krs
    )
    if all_done:
        obj.status = "completed"
        await session.flush()
        return True
    return False


async def get_next_unblocked_action(
    session: AsyncSession,
    user_id: int,
    completed_task: Optional[Task] = None,
) -> Optional[dict]:
    """Return the highest-priority next unblocked task as a dict.

    Priority order:
    1. Next todo task in the same Key Result (if task was KR-linked)
    2. Next todo task in the same Objective
    3. Global top unblocked task for the user
    """
    # Helper: task → serializable dict
    def _task_dict(t: Task, source: str) -> dict:
        return {
            "id": t.id,
            "title": t.title,
            "priority": t.priority,
            "due_date": t.due_date.isoformat() if t.due_date else None,
            "key_result_id": t.key_result_id,
            "objective_id": t.objective_id,
            "source": source,
            "reason": get_task_reason(t),
        }

    # 1. Same KR
    if completed_task and completed_task.key_result_id:
        kr_res = await session.execute(
            select(Task)
            .where(and_(
                Task.key_result_id == completed_task.key_result_id,
                Task.status == "todo",
                Task.blocked_by_task_id.is_(None),
            ))
            .order_by(Task.priority.asc(), Task.created_at.asc())
            .limit(1)
        )
        t = kr_res.scalar_one_or_none()
        if t:
            return _task_dict(t, "same_kr")

    # 2. Same Objective
    if completed_task and completed_task.objective_id:
        obj_res = await session.execute(
            select(Task)
            .where(and_(
                Task.objective_id == completed_task.objective_id,
                Task.status == "todo",
                Task.blocked_by_task_id.is_(None),
            ))
            .order_by(Task.priority.asc(), Task.created_at.asc())
            .limit(1)
        )
        t = obj_res.scalar_one_or_none()
        if t:
            return _task_dict(t, "same_objective")

    # 3. Global top unblocked task
    global_res = await session.execute(
        select(Task)
        .where(and_(
            Task.user_id == user_id,
            Task.status == "todo",
            Task.category != "shopping",
            Task.blocked_by_task_id.is_(None),
        ))
        .order_by(Task.priority.asc(), Task.due_date.asc().nulls_last(), Task.created_at.asc())
        .limit(1)
    )
    t = global_res.scalar_one_or_none()
    if t:
        return _task_dict(t, "global")

    return None
