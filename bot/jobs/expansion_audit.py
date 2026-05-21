"""V3 P08 — Weekly expansion audit (Sunday 18:00 Berlin).

For every active user: count active Objectives + Priority-1 Objectives.
If either limit is exceeded, send a Coach-Modus message naming the
weakest objective and the `/cut <id>` command.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import settings
from bot.core.objectives import (
    PRIORITY1_THRESHOLD,
    suggest_objective_to_cut,
)
from bot.database.connection import get_session
from bot.database.models import AutopilotNotification, Objective, User

logger = logging.getLogger(__name__)


async def run_weekly_expansion_audit() -> None:
    """Sunday-18:00 sweep. Idempotent within a 24h window via AutopilotNotification."""
    now = datetime.utcnow()
    day_ago = now - timedelta(hours=24)

    async with get_session() as session:
        users = (await session.execute(
            select(User).where(User.is_active == True)  # noqa: E712
        )).scalars().all()

        for user in users:
            try:
                await _audit_user(session, user, day_ago)
            except Exception:
                logger.exception("expansion audit failed for user %s", user.id)


async def _audit_user(session: AsyncSession, user: User, day_ago: datetime) -> None:
    active = (await session.execute(
        select(Objective).where(and_(
            Objective.user_id == user.id,
            Objective.status == "active",
        ))
    )).scalars().all()
    total = len(active)
    priority1 = sum(1 for o in active if (o.priority_weight or 0) >= PRIORITY1_THRESHOLD)

    soft = settings.expansion_soft_limit_priority1
    hard = settings.expansion_hard_limit_total

    if priority1 < soft and total < hard:
        return

    # Idempotency: don't double-fire within 24h
    existing = (await session.execute(
        select(AutopilotNotification).where(and_(
            AutopilotNotification.user_id == user.id,
            AutopilotNotification.notification_type == "expansion_audit",
            AutopilotNotification.created_at >= day_ago,
        )).limit(1)
    )).scalar_one_or_none()
    if existing is not None:
        return

    cut = await suggest_objective_to_cut(session, user.id)

    headline_parts: list[str] = []
    if priority1 >= soft:
        headline_parts.append(f"{priority1} Priority-1-Ziele (Limit {soft})")
    if total >= hard:
        headline_parts.append(f"{total} aktive Ziele (Hard-Limit {hard})")
    headline = "Wochen-Audit: " + ", ".join(headline_parts) + "."

    body_lines = [headline]
    if cut:
        body_lines.append(
            f"Schwächstes: '{cut['title']}' ({cut['days_stale']}d ohne Log, "
            f"{int(cut['completion']*100)}% erfüllt)."
        )
        body_lines.append(f"Cut: /cut {cut['id']}")
    body_text = "\n".join(body_lines)

    # Persist a notification (visible in dashboard + idempotency marker)
    session.add(AutopilotNotification(
        user_id=user.id,
        notification_type="expansion_audit",
        title="Expansionsschutz: Cut nötig",
        body=body_text,
        status="pending",
        source="expansion_audit",
    ))
    await session.flush()

    # Best-effort Telegram delivery — quiet hours respected by send_message itself
    try:
        from bot.telegram.sender import send_message
        await send_message(user.telegram_id, body_text)
    except Exception:
        logger.exception("expansion audit Telegram send failed for user %s", user.id)

    await session.commit()
