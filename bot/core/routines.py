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
    schedule_cron: str,
    frequency_human: str,
    linked_key_result_id: Optional[int] = None,
    description: Optional[str] = None,
) -> Routine:
    """Create a new Routine."""
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
    # Check routine exists and belongs to user
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
        logged_via="telegram",
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
    return result.scalars().all()


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
