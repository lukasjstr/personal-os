"""Phase 3: User insights — pattern detection and reflection-derived learnings."""
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
    """Create a new user insight.

    Phase 3: insight_type is one of: productivity_pattern, habit, blocker, strength, preference.
    source is one of: reflection, auto_detected, user_stated.
    """
    raise NotImplementedError("Phase 3")


async def get_active_insights(session: AsyncSession, user_id: int) -> list[UserInsight]:
    """Get all active insights for a user.

    Phase 3: Returns insights with active=True, ordered by created_at desc.
    These are included in morning briefs for personalized advice.
    """
    raise NotImplementedError("Phase 3")


async def detect_patterns(session: AsyncSession, user_id: int) -> list[dict]:
    """Auto-detect behavioral patterns from logs and completions.

    Phase 3: Analyzes mood correlations, productive time-of-day,
    streak patterns, and completion rate trends.
    Returns list of detected pattern dicts to create insights from.
    """
    raise NotImplementedError("Phase 3")
