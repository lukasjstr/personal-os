"""Phase 2: Morning brief generation and sending.

Sends personalized daily plan to each user at their configured morning_brief_time.
Includes top 3 priorities, routine checklist, calendar events, and warnings.
"""
import logging

logger = logging.getLogger(__name__)


async def send_morning_brief() -> None:
    """Send morning brief to all active users whose brief time has arrived.

    Phase 2: Iterates all active users, checks if morning_brief_time matches
    current hour:minute, generates AI brief with priorities and context,
    sends via Telegram.
    """
    raise NotImplementedError("Phase 2")


async def _generate_brief_for_user(user_id: int) -> str:
    """Generate personalized morning brief text for a user.

    Phase 2: Uses GPT-4o-mini with user context to generate:
    - Top 3 priorities with brief explanation
    - Today's routines
    - Calendar events
    - Proactive warnings (overdue tasks, streak risks)
    - Motivational nudge based on yesterday's performance
    """
    raise NotImplementedError("Phase 2")
