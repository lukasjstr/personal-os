"""Conversation history helpers."""
from datetime import date, timedelta
from typing import Optional

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import Conversation


async def save_conversation(
    session: AsyncSession,
    user_id: int,
    role: str,
    content: str,
    tool_calls: Optional[dict] = None,
    tokens_used: Optional[int] = None,
    session_date: Optional[date] = None,
) -> Conversation:
    """Save a conversation turn."""
    conv = Conversation(
        user_id=user_id,
        role=role,
        content=content,
        extra_data=tool_calls,
        tokens_used=tokens_used,
        session_date=session_date or date.today(),
    )
    session.add(conv)
    await session.flush()
    return conv


async def get_recent_conversations(
    session: AsyncSession,
    user_id: int,
    limit: int = 10,
) -> list[dict]:
    """Get recent conversations as dicts for AI message history.
    Returns today's conversations; if fewer than 3, includes yesterday's too.
    """
    today = date.today()

    result = await session.execute(
        select(Conversation)
        .where(and_(
            Conversation.user_id == user_id,
            Conversation.session_date == today,
        ))
        .order_by(Conversation.created_at.desc())
        .limit(limit)
    )
    convs = list(reversed(result.scalars().all()))

    if len(convs) < 3:
        yesterday = today - timedelta(days=1)
        result2 = await session.execute(
            select(Conversation)
            .where(and_(
                Conversation.user_id == user_id,
                Conversation.session_date == yesterday,
            ))
            .order_by(Conversation.created_at.desc())
            .limit(limit - len(convs))
        )
        yesterday_convs = list(reversed(result2.scalars().all()))
        convs = yesterday_convs + convs

    return [{"role": c.role, "content": c.content} for c in convs]
