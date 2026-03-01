"""Morning brief cron job — sends daily plan at 06:30."""
import logging
from datetime import date, datetime

from openai import AsyncOpenAI
from sqlalchemy import select

from bot.ai.context import build_context
from bot.ai.prompts import MORNING_BRIEF_PROMPT
from bot.config import settings
from bot.core.priorities import get_todays_priorities
from bot.database.connection import get_session
from bot.database.models import User
from bot.telegram.sender import send_message

logger = logging.getLogger(__name__)

openai_client = AsyncOpenAI(api_key=settings.openai_api_key)


async def send_morning_brief() -> None:
    """Send morning brief to all active users."""
    logger.info("Running morning brief job")
    async with get_session() as session:
        result = await session.execute(select(User))
        users = result.scalars().all()

    for user in users:
        try:
            await _send_brief_to_user(user)
        except Exception as e:
            logger.exception("Morning brief failed for user %s: %s", user.id, e)


async def _send_brief_to_user(user: User) -> None:
    """Generate and send morning brief to a specific user."""
    async with get_session() as session:
        context = await build_context(session, user)
        priorities = await get_todays_priorities(session, user.id)

    response = await openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": MORNING_BRIEF_PROMPT},
            {"role": "user", "content": f"Kontext:\n{context}\n\nPrioritäten:\n{priorities}"},
        ],
        max_tokens=600,
        temperature=0.5,
    )
    brief = response.choices[0].message.content or ""
    greeting = f"☀️ Guten Morgen!\n\n{brief}"
    await send_message(user.telegram_id, greeting)
    logger.info("Morning brief sent to user %s", user.id)
