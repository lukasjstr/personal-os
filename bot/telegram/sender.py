"""Telegram message sending utilities."""
import logging
from typing import Optional

from telegram import Bot
from telegram.constants import ParseMode
from telegram.error import TelegramError

from bot.config import settings
from bot.telegram.formatting import truncate

logger = logging.getLogger(__name__)

_bot: Optional[Bot] = None


def get_bot() -> Bot:
    """Return the singleton Bot instance."""
    global _bot
    if _bot is None:
        _bot = Bot(token=settings.telegram_bot_token)
    return _bot


async def send_message(
    chat_id: int,
    text: str,
    parse_mode: Optional[str] = None,
) -> bool:
    """Send a text message to a Telegram chat."""
    bot = get_bot()
    text = truncate(text)
    try:
        await bot.send_message(chat_id=chat_id, text=text, parse_mode=parse_mode)
        return True
    except TelegramError as e:
        logger.error("Failed to send message to %s: %s", chat_id, e)
        return False


async def send_typing(chat_id: int) -> None:
    """Send typing action."""
    bot = get_bot()
    try:
        await bot.send_chat_action(chat_id=chat_id, action="typing")
    except TelegramError:
        pass
