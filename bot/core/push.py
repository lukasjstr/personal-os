"""Web Push notification sender using pywebpush.

Sends push notifications to all registered PushSubscription endpoints
for a given user. Handles expired subscriptions (410 Gone) gracefully.
"""
from __future__ import annotations

import json
import logging
from typing import Optional

from sqlalchemy import and_, delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import settings
from bot.database.models import PushSubscription

logger = logging.getLogger(__name__)


async def send_push(
    session: AsyncSession,
    user_id: int,
    title: str,
    body: str,
    url: Optional[str] = None,
    tag: Optional[str] = None,
) -> int:
    """Send web push to all user subscriptions. Returns count of successful sends.

    Non-fatal: logs errors but never raises.
    """
    if not settings.vapid_private_key or not settings.vapid_public_key:
        return 0

    subs = (await session.execute(
        select(PushSubscription).where(PushSubscription.user_id == user_id)
    )).scalars().all()

    if not subs:
        return 0

    payload = json.dumps({
        "title": title,
        "body": body,
        "url": url or "/",
        "tag": tag or "personal-os",
        "icon": "/icons/icon-192x192.png",
        "badge": "/icons/icon-192x192.png",
    })

    sent = 0
    expired_ids: list[int] = []

    for sub in subs:
        try:
            from pywebpush import webpush, WebPushException  # type: ignore[import-untyped]
            webpush(
                subscription_info={
                    "endpoint": sub.endpoint,
                    "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
                },
                data=payload,
                vapid_private_key=settings.vapid_private_key,
                vapid_claims={
                    "sub": settings.vapid_mailto,
                },
            )
            sent += 1
        except Exception as exc:
            # Check for 410 Gone (subscription expired)
            exc_str = str(exc)
            if "410" in exc_str or "Gone" in exc_str:
                expired_ids.append(sub.id)
                logger.info("Push subscription expired (410): sub_id=%d", sub.id)
            else:
                logger.warning("Push send failed for sub_id=%d: %s", sub.id, exc_str)

    # Clean up expired subscriptions
    if expired_ids:
        await session.execute(
            delete(PushSubscription).where(PushSubscription.id.in_(expired_ids))
        )
        await session.flush()

    if sent:
        logger.info("Push sent to %d/%d subscriptions for user %d", sent, len(subs), user_id)
    return sent


async def send_push_if_subscribed(
    session: AsyncSession,
    user_id: int,
    title: str,
    body: str,
    url: Optional[str] = None,
    tag: Optional[str] = None,
) -> int:
    """Convenience wrapper — only attempts push if VAPID keys are configured."""
    if not settings.vapid_private_key:
        return 0
    return await send_push(session, user_id, title, body, url=url, tag=tag)
