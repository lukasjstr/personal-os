"""Phase 2: Daily brief creation and management.
Handles morning brief generation, evening review, and day scoring.
"""
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import DailyBrief


async def create_daily_brief(session: AsyncSession, user_id: int) -> DailyBrief:
    """Create today's daily brief with priorities, routines, calendar events, and warnings.

    Phase 2: Generates AI-powered brief with top 3 priorities, routine checklist,
    calendar events for the day, and proactive warnings (overdue tasks, streak risks).
    """
    raise NotImplementedError("Phase 2")


async def get_todays_brief(session: AsyncSession, user_id: int) -> Optional[DailyBrief]:
    """Get today's daily brief for a user, if it exists.

    Phase 2: Returns the DailyBrief record for today's date, or None if not yet created.
    """
    raise NotImplementedError("Phase 2")


async def update_brief_priorities(
    session: AsyncSession,
    brief_id: int,
    priorities: list[dict],
) -> DailyBrief:
    """Update user-adjusted priorities for a daily brief.

    Phase 2: Allows user to reorder or change their top 3 priorities for the day.
    Sets user_adjusted=True and stores adjusted_priorities.
    """
    raise NotImplementedError("Phase 2")


async def save_day_score(
    session: AsyncSession,
    brief_id: int,
    score: int,
    notes: Optional[str] = None,
) -> DailyBrief:
    """Save the end-of-day score (1-10) during evening review.

    Phase 2: Records day_score and day_notes, marks review as done.
    """
    raise NotImplementedError("Phase 2")
