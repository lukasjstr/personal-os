"""V3 P09 — Friday-Cut scheduler entry.

Runs every Friday 17:00 Berlin. For each active user: build the cut prompt,
send it via Telegram, and flip the user into 'friday_cut' pending state so
the next text reply is interpreted as a cut decision.
"""
from __future__ import annotations

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select

from bot.core.friday_cut import build_friday_cut_prompt
from bot.core.smart_detector import set_pending_prompt
from bot.database.connection import get_session
from bot.database.models import User
from bot.telegram.sender import send_message

logger = logging.getLogger(__name__)


async def run_friday_cut() -> None:
    """Send the Friday-Cut prompt to all active users (Friday 17:00 Berlin)."""
    now_berlin = datetime.now(tz=ZoneInfo("Europe/Berlin"))
    today = now_berlin.date()

    async with get_session() as session:
        users = (await session.execute(
            select(User).where(User.is_active == True)  # noqa: E712
        )).scalars().all()

        for user in users:
            try:
                msg = await build_friday_cut_prompt(session, user.id, today)
                ok = await send_message(user.telegram_id, msg)
                if ok:
                    set_pending_prompt(user.id, "friday_cut")
                    logger.info("Friday-Cut prompt sent to user %s", user.id)
            except Exception:
                logger.exception("Friday-Cut send failed for user %s", user.id)
