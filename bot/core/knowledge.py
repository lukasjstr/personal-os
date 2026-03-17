"""Spaced Repetition + Knowledge Management using SM-2 algorithm."""
import logging
from datetime import datetime, timedelta
from typing import Optional

from openai import AsyncOpenAI
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import settings
from bot.database.models import LearningItem, LearningReview

logger = logging.getLogger(__name__)
_openai = AsyncOpenAI(api_key=settings.openai_api_key)

# SM-2 base intervals in days for quality >= 3 (first two reps)
SM2_INTERVALS = [1, 6]


async def add_learning_item(
    session: AsyncSession,
    user_id: int,
    title: str,
    content: str,
    item_type: str,
    source: Optional[str] = None,
    tags: Optional[list] = None,
) -> LearningItem:
    """Add item. If item_type in ('book','article'): auto-generate ai_summary via GPT-4o-mini."""
    ai_summary = None
    if item_type in ("book", "article") and content:
        try:
            resp = await _openai.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{
                    "role": "user",
                    "content": (
                        f"Erstelle eine kompakte Zusammenfassung (max 150 Wörter) auf Deutsch "
                        f"für folgendes {item_type}:\n\nTitel: {title}\n\n{content[:2000]}"
                    ),
                }],
                max_tokens=300,
                temperature=0.5,
            )
            ai_summary = resp.choices[0].message.content
        except Exception:
            logger.exception("AI summary generation failed for learning item")

    next_review = datetime.utcnow() + timedelta(days=1)
    item = LearningItem(
        user_id=user_id,
        title=title,
        content=content,
        item_type=item_type,
        source=source,
        tags=tags or [],
        ai_summary=ai_summary,
        next_review_at=next_review,
        ease_factor=2.5,
        review_count=0,
        skill_level=1,
    )
    session.add(item)
    await session.flush()
    return item


async def review_item(
    session: AsyncSession,
    user_id: int,
    item_id: int,
    quality: int,
) -> dict:
    """SM-2 algorithm: update ease_factor and next_review_at.

    quality 0-2: failed, reset interval
    quality 3-5: passed, increase interval
    Returns {'next_review_in_days': n, 'new_level': n}
    """
    res = await session.execute(
        select(LearningItem).where(and_(
            LearningItem.id == item_id,
            LearningItem.user_id == user_id,
        ))
    )
    item = res.scalar_one_or_none()
    if not item:
        return {"error": "Item not found"}

    quality = max(0, min(5, quality))

    # SM-2 algorithm
    review_count = item.review_count or 0
    ease = item.ease_factor or 2.5

    if quality < 3:
        # Failed: reset to beginning
        next_interval_days = SM2_INTERVALS[0]
        # Don't change ease factor on failure (or optionally reduce)
    else:
        # Passed: calculate next interval
        if review_count == 0:
            next_interval_days = SM2_INTERVALS[0]
        elif review_count == 1:
            next_interval_days = SM2_INTERVALS[1]
        else:
            # Use last interval * ease_factor
            # Approximate last interval from review_count
            prev_interval = SM2_INTERVALS[1]
            for _ in range(review_count - 1):
                prev_interval = max(1, round(prev_interval * ease))
            next_interval_days = max(1, round(prev_interval * ease))

        # Update ease factor: EF' = EF + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02))
        ease_delta = 0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)
        ease = max(1.3, ease + ease_delta)

    item.ease_factor = round(ease, 3)
    item.review_count = review_count + 1
    item.last_reviewed_at = datetime.utcnow()
    item.next_review_at = datetime.utcnow() + timedelta(days=next_interval_days)

    # Update skill level based on review count and quality
    if quality >= 4 and item.item_type == "skill":
        new_level = min(5, max(1, (item.review_count // 3) + 1))
        item.skill_level = new_level

    # Record review
    review = LearningReview(
        user_id=user_id,
        item_id=item_id,
        quality=quality,
    )
    session.add(review)
    await session.flush()

    return {
        "next_review_in_days": next_interval_days,
        "new_level": item.skill_level,
        "new_ease": item.ease_factor,
        "review_count": item.review_count,
    }


async def get_due_reviews(session: AsyncSession, user_id: int) -> list[LearningItem]:
    """Items where next_review_at <= now."""
    res = await session.execute(
        select(LearningItem).where(and_(
            LearningItem.user_id == user_id,
            LearningItem.next_review_at <= datetime.utcnow(),
        )).order_by(LearningItem.next_review_at.asc())
    )
    return res.scalars().all()


async def get_weekly_learning_summary(session: AsyncSession, user_id: int) -> str:
    """Return what was learned/reviewed this week for weekly reflection."""
    since = datetime.utcnow() - timedelta(days=7)
    res = await session.execute(
        select(LearningReview).where(and_(
            LearningReview.user_id == user_id,
            LearningReview.reviewed_at >= since,
        ))
    )
    reviews = res.scalars().all()
    if not reviews:
        return ""

    # Count unique items reviewed
    item_ids = set(r.item_id for r in reviews)
    items_res = await session.execute(
        select(LearningItem).where(LearningItem.id.in_(item_ids))
    )
    items = items_res.scalars().all()

    lines = [f"📚 Lernen diese Woche: {len(reviews)} Wiederholungen, {len(items)} verschiedene Items"]
    for item in items[:5]:
        lines.append(f"  - {item.title} ({item.item_type})")
    return "\n".join(lines)


async def get_knowledge_context(session: AsyncSession, user_id: int) -> str:
    """Return active skills + items due for review as AI context block."""
    # Due items
    due = await get_due_reviews(session, user_id)

    # Active skills
    skills_res = await session.execute(
        select(LearningItem).where(and_(
            LearningItem.user_id == user_id,
            LearningItem.item_type == "skill",
        )).order_by(LearningItem.skill_level.desc()).limit(10)
    )
    skills = skills_res.scalars().all()

    if not due and not skills:
        return ""

    lines = ["=== WISSEN & LERNEN ==="]

    if due:
        lines.append(f"Fällige Wiederholungen: {len(due)}")
        for item in due[:3]:
            lines.append(f"  📖 {item.title} ({item.item_type})")

    if skills:
        lines.append("Skills:")
        for s in skills[:5]:
            level_bar = "█" * s.skill_level + "░" * (5 - s.skill_level)
            lines.append(f"  {s.title}: [{level_bar}] Lv.{s.skill_level}")

    return "\n".join(lines)
