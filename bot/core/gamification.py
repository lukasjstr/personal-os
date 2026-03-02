"""XP and leveling system for Personal OS — Phase 7.2."""
import logging
import math

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import User

logger = logging.getLogger(__name__)

LEVEL_TITLES = [
    "Rookie", "Beginner", "Learner", "Achiever", "Warrior",
    "Champion", "Master", "Expert", "Elite", "Legend", "Myth",
]


def get_level(xp: int) -> int:
    """Compute level from total XP. Level = floor(sqrt(xp / 100))."""
    return math.floor(math.sqrt(xp / 100)) if xp > 0 else 0


def get_xp_for_next_level(level: int) -> int:
    """Total XP required to reach the next level."""
    return (level + 1) ** 2 * 100


def get_level_title(level: int) -> str:
    return LEVEL_TITLES[min(level, len(LEVEL_TITLES) - 1)]


async def add_xp(
    user_id: int,
    amount: int,
    reason: str,
    session: AsyncSession,
) -> tuple[int, int, bool, int]:
    """Add XP to a user.

    Returns:
        (new_xp, new_level, leveled_up, old_level)
    """
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        logger.warning("add_xp: user %s not found", user_id)
        return 0, 0, False, 0

    old_xp = user.xp or 0
    old_level = get_level(old_xp)

    user.xp = old_xp + amount
    new_level = get_level(user.xp)
    leveled_up = new_level > old_level
    if leveled_up:
        user.level = new_level

    await session.flush()

    logger.info(
        "XP +%d (%s) → user=%s total=%d level=%d%s",
        amount, reason, user_id, user.xp, new_level,
        " [LEVEL UP!]" if leveled_up else "",
    )
    return user.xp, new_level, leveled_up, old_level
