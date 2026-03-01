"""Phase 2: Evening review generation and sending.

Sends end-of-day review to each user at their configured evening_review_time.
Includes completion summary, mood check, and tomorrow's preview.
"""
import logging

logger = logging.getLogger(__name__)


async def send_evening_review() -> None:
    """Send evening review to all active users whose review time has arrived.

    Phase 2: Iterates all active users with review_enabled=True,
    checks if evening_review_time matches current time,
    generates AI review with completion stats, requests day score,
    previews tomorrow.
    """
    raise NotImplementedError("Phase 2")


async def _generate_review_for_user(user_id: int) -> str:
    """Generate personalized evening review text for a user.

    Phase 2: Summarizes:
    - Tasks completed vs planned
    - Routines completed
    - Workouts / water logged
    - Asks for mood rating (1-10)
    - Preview of tomorrow's top priorities
    - Completion rate trend (this week)
    """
    raise NotImplementedError("Phase 2")
