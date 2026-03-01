"""Phase 3: Weekly reflection invitation trigger.

Sends reflection invitation every Sunday evening at the user's configured time.
"""
import logging

logger = logging.getLogger(__name__)


async def check_and_trigger_reflections() -> None:
    """Check if it's Sunday at the reflection time for any user and invite them.

    Phase 3: Iterates all active users with reflection_enabled=True.
    If today is the user's weekly_reflection_day and time matches,
    sends invitation: 'Willst du reflektieren? [Ja] [Nein]'.
    Waits for response before starting guided session.
    """
    raise NotImplementedError("Phase 3")


async def send_reflection_invitation(user_id: int) -> None:
    """Send the weekly reflection invitation to a specific user.

    Phase 3: Sends friendly invite message with opt-in/skip options.
    If user responds 'Ja': triggers start_reflection().
    If user responds 'Nein' or no response within 2 hours: skips quietly.
    """
    raise NotImplementedError("Phase 3")
