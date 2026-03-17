"""User insights — pattern detection and reflection-derived learnings."""
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import UserInsight


async def create_insight(
    session: AsyncSession,
    user_id: int,
    insight_type: str,
    title: str,
    description: str,
    source: str,
    data_basis: dict | None = None,
) -> UserInsight:
    """Create a new user insight."""
    insight = UserInsight(
        user_id=user_id,
        insight_type=insight_type,
        title=title,
        description=description,
        source=source,
        active=True,
        data_basis=data_basis or {},
    )
    session.add(insight)
    await session.flush()
    return insight


async def get_active_insights(session: AsyncSession, user_id: int) -> list[UserInsight]:
    """Get all active insights for a user, newest first."""
    result = await session.execute(
        select(UserInsight).where(and_(
            UserInsight.user_id == user_id,
            UserInsight.active == True,  # noqa: E712
        )).order_by(UserInsight.created_at.desc()).limit(10)
    )
    return list(result.scalars().all())


async def detect_patterns(session: AsyncSession, user_id: int) -> list[dict]:
    """Run pattern analysis and return detected patterns."""
    from bot.core.pattern_engine import run_pattern_analysis
    result = await run_pattern_analysis(session, user_id)
    return result.get("insights", [])
