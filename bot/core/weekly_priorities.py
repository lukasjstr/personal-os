"""Phase 3: Weekly priority management.
Priorities set during Sunday reflection override auto-prioritization.
"""
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import WeeklyPriority


async def set_priorities(
    session: AsyncSession,
    user_id: int,
    priorities: list[dict],
) -> list[WeeklyPriority]:
    """Set weekly priorities for the current week.

    Phase 3: priorities is a list of dicts with keys: title, rank (1-3),
    and optionally linked_objective_id, linked_key_result_id, linked_task_id.
    Replaces existing active priorities for this week.
    """
    raise NotImplementedError("Phase 3")


async def get_current_priorities(
    session: AsyncSession,
    user_id: int,
) -> list[WeeklyPriority]:
    """Get active weekly priorities for the current week.

    Phase 3: Returns up to 3 WeeklyPriority records ordered by priority_rank.
    These override auto-calculated priorities in morning briefs.
    """
    raise NotImplementedError("Phase 3")


async def complete_priority(session: AsyncSession, priority_id: int) -> WeeklyPriority:
    """Mark a weekly priority as completed.

    Phase 3: Sets status='completed'. Triggers celebration in next morning brief.
    """
    raise NotImplementedError("Phase 3")
