"""Weekly pattern analysis job — runs every Sunday morning."""
import logging

from sqlalchemy import select

from bot.database.connection import get_session
from bot.database.models import User

logger = logging.getLogger(__name__)


async def run_weekly_pattern_analysis() -> None:
    """Run pattern analysis for all active users. Triggered Sunday 08:30."""
    async with get_session() as session:
        users_result = await session.execute(
            select(User).where(User.is_active == True)  # noqa: E712
        )
        users = users_result.scalars().all()

        for user in users:
            try:
                from bot.core.pattern_engine import run_pattern_analysis
                result = await run_pattern_analysis(session, user.id)
                await session.commit()
                logger.info(
                    "Pattern analysis complete for user %s: %d insights",
                    user.id, len(result.get("insights", []))
                )
            except Exception:
                logger.exception("Pattern analysis failed for user %s", user.id)
