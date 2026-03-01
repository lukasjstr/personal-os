"""Brain dump storage and retrieval."""
from typing import Optional

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import BrainDump


async def create_brain_dump(
    session: AsyncSession,
    user_id: int,
    content: str,
    linked_objective_id: Optional[int] = None,
    ai_interpretation: Optional[str] = None,
) -> BrainDump:
    """Store an unstructured brain dump."""
    bd = BrainDump(
        user_id=user_id,
        raw_input=content,
        linked_objective_id=linked_objective_id,
        ai_interpretation=ai_interpretation,
        processed=False,
    )
    session.add(bd)
    await session.flush()
    return bd


async def get_unprocessed_brain_dumps(
    session: AsyncSession,
    user_id: int,
) -> list[BrainDump]:
    """Get all unprocessed brain dumps for a user."""
    result = await session.execute(
        select(BrainDump)
        .where(and_(BrainDump.user_id == user_id, BrainDump.processed == False))  # noqa: E712
        .order_by(BrainDump.created_at.desc())
    )
    return result.scalars().all()


async def get_all_brain_dumps(
    session: AsyncSession,
    user_id: int,
    limit: int = 50,
) -> list[BrainDump]:
    """Get brain dumps for a user."""
    result = await session.execute(
        select(BrainDump)
        .where(BrainDump.user_id == user_id)
        .order_by(BrainDump.created_at.desc())
        .limit(limit)
    )
    return result.scalars().all()
