"""Routine CRUD and completion tracking."""
from datetime import datetime, date
from typing import Optional

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import Routine, RoutineCompletion


async def create_routine(
    session: AsyncSession,
    user_id: int,
    title: str,
    frequency_human: str,
    schedule_cron: Optional[str] = None,
    linked_key_result_id: Optional[int] = None,
    description: Optional[str] = None,
) -> Routine:
    """Create a new Routine. schedule_cron is optional."""
    routine = Routine(
        user_id=user_id,
        title=title,
        description=description,
        schedule_cron=schedule_cron,
        frequency_human=frequency_human,
        linked_key_result_id=linked_key_result_id,
        status="active",
    )
    session.add(routine)
    await session.flush()
    return routine


async def complete_routine(
    session: AsyncSession,
    user_id: int,
    routine_id: int,
    notes: Optional[str] = None,
) -> Optional[RoutineCompletion]:
    """Mark a routine as completed for today."""
    result = await session.execute(
        select(Routine).where(
            and_(Routine.id == routine_id, Routine.user_id == user_id)
        )
    )
    routine = result.scalar_one_or_none()
    if not routine:
        return None

    completion = RoutineCompletion(
        routine_id=routine_id,
        user_id=user_id,
        completed_at=datetime.utcnow(),
        notes=notes,
    )
    session.add(completion)
    await session.flush()
    return completion


async def get_active_routines(session: AsyncSession, user_id: int) -> list[Routine]:
    """Get all active routines for a user."""
    result = await session.execute(
        select(Routine).where(
            and_(Routine.user_id == user_id, Routine.status == "active")
        )
    )
    return list(result.scalars().all())


async def get_todays_completions(session: AsyncSession, user_id: int) -> set[int]:
    """Get routine IDs completed today."""
    today_start = datetime.combine(date.today(), datetime.min.time())
    result = await session.execute(
        select(RoutineCompletion.routine_id).where(
            and_(
                RoutineCompletion.user_id == user_id,
                RoutineCompletion.completed_at >= today_start,
            )
        )
    )
    return set(result.scalars().all())


async def is_done_today(session: AsyncSession, routine_id: int) -> bool:
    """Check if a routine was completed today."""
    today_start = datetime.combine(date.today(), datetime.min.time())
    result = await session.execute(
        select(RoutineCompletion).where(
            and_(
                RoutineCompletion.routine_id == routine_id,
                RoutineCompletion.completed_at >= today_start,
            )
        ).limit(1)
    )
    return result.scalar_one_or_none() is not None


async def get_todays_routines_with_status(
    session: AsyncSession,
    user_id: int,
) -> list[tuple[Routine, bool]]:
    """Return list of (routine, is_done_today) for all active routines."""
    routines = await get_active_routines(session, user_id)
    completed_ids = await get_todays_completions(session, user_id)
    return [(r, r.id in completed_ids) for r in routines]
