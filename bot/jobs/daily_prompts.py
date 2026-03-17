"""Daily proactive prompts for journal and gratitude practices.

Scheduled jobs:
- 07:30: Journal prompt
- 21:15: Gratitude prompt
"""
import logging

from sqlalchemy import select

from bot.database.connection import get_session
from bot.database.models import User
from bot.telegram.sender import send_message

logger = logging.getLogger(__name__)


async def send_journal_prompts() -> None:
    """07:30 daily: send journal prompt to all active users."""
    from bot.core.smart_detector import set_pending_prompt
    from bot.telegram.sender import get_bot
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    async with get_session() as session:
        result = await session.execute(select(User).where(User.is_active == True))  # noqa: E712
        users = result.scalars().all()

        bot = get_bot()
        for user in users:
            try:
                set_pending_prompt(user.id, "journal")
                keyboard = InlineKeyboardMarkup([[
                    InlineKeyboardButton("✍️ Jetzt schreiben", callback_data="prompt_journal_open"),
                    InlineKeyboardButton("⏭ Später", callback_data="prompt_skip"),
                ]])
                await bot.send_message(
                    chat_id=user.telegram_id,
                    text=(
                        "📓 *Morgen-Journal*\n\n"
                        "Nimm dir 5–10 Minuten. Schreib einfach los:\n\n"
                        "• Was hast du gestern gelernt?\n"
                        "• Was willst du heute erreichen?\n"
                        "• Was macht dir gerade Sorgen?\n\n"
                        "_Schick deine Antwort direkt hier — ich speichere sie automatisch._"
                    ),
                    parse_mode="Markdown",
                    reply_markup=keyboard,
                )
                logger.info("Journal prompt sent to user %d", user.id)
            except Exception:
                logger.exception("Journal prompt failed for user %d", user.id)


async def send_gratitude_prompts() -> None:
    """21:15 daily: send gratitude prompt to all active users."""
    from bot.core.smart_detector import set_pending_prompt
    from bot.telegram.sender import get_bot
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    async with get_session() as session:
        result = await session.execute(select(User).where(User.is_active == True))  # noqa: E712
        users = result.scalars().all()

        bot = get_bot()
        for user in users:
            try:
                keyboard = InlineKeyboardMarkup([[
                    InlineKeyboardButton("✍️ Jetzt schreiben", callback_data="prompt_gratitude_open"),
                    InlineKeyboardButton("⏭ Überspringen", callback_data="prompt_skip"),
                ]])
                await bot.send_message(
                    chat_id=user.telegram_id,
                    text=(
                        "🙏 *Abend-Dankbarkeit*\n\n"
                        "Nenne 3 Dinge für die du heute dankbar bist.\n\n"
                        "_Schick sie einfach hier oder klick auf Jetzt schreiben — ich speichere alles automatisch._"
                    ),
                    parse_mode="Markdown",
                    reply_markup=keyboard,
                )
                logger.info("Gratitude prompt sent to user %d", user.id)
            except Exception:
                logger.exception("Gratitude prompt failed for user %d", user.id)
