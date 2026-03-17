"""Fitness KR Sync — links workout logs to Key Results automatically.

When a workout is logged, find the matching fitness KR and increment it.
This closes the loop: User logs workout → Fitness KR updated automatically.
"""
import logging
from typing import Optional

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import KeyResult, User, WorkoutLog

logger = logging.getLogger(__name__)

# Keywords to match workout logs to KR types
CARDIO_KEYWORDS = ["lauf", "run", "cardio", "rad", "bike", "schwimm", "swim", "hiit", "fahrrad"]
STRENGTH_KEYWORDS = ["kraft", "gym", "training", "workout", "bench", "squat", "deadlift",
                     "bankdrück", "kniebeu", "kreuzheb", "hang", "pull", "push", "dip",
                     "bizeps", "trizeps", "schulter", "brust", "rücken"]


def _is_cardio(exercise_name: str) -> bool:
    name = exercise_name.lower()
    return any(kw in name for kw in CARDIO_KEYWORDS)


def _is_strength(exercise_name: str) -> bool:
    name = exercise_name.lower()
    return any(kw in name for kw in STRENGTH_KEYWORDS)


async def sync_workout_to_kr(
    session: AsyncSession,
    user: User,
    workout_log: WorkoutLog,
) -> Optional[str]:
    """After a workout is logged, find and update the matching KR.

    Returns a brief message about the KR update, or None.
    """
    if not workout_log or not workout_log.exercise:
        return None

    exercise_name = workout_log.exercise or ""

    # Determine workout type from exercise name
    is_cardio = _is_cardio(exercise_name)
    is_strength = _is_strength(exercise_name)

    # Fall back: if it has weight/sets/reps it's strength
    if not is_cardio and not is_strength:
        if workout_log.weight_kg or workout_log.sets or workout_log.reps:
            is_strength = True
        else:
            is_strength = True  # default to strength

    # Find matching KR
    kr_res = await session.execute(
        select(KeyResult).where(and_(
            KeyResult.user_id == user.id,
            KeyResult.status == "active",
        ))
    )
    krs = kr_res.scalars().all()

    matched_kr: Optional[KeyResult] = None
    for kr in krs:
        title_lower = kr.title.lower()
        if is_cardio and any(kw in title_lower for kw in ["cardio", "ausdauer", "lauf", "laufen"]):
            matched_kr = kr
            break
        if is_strength and any(kw in title_lower for kw in ["kraft", "training", "gym", "workout"]):
            matched_kr = kr
            break

    if not matched_kr:
        # Try generic fitness KR
        for kr in krs:
            if any(kw in kr.title.lower() for kw in ["sport", "fitness", "einheit", "workout"]):
                matched_kr = kr
                break

    if not matched_kr:
        return None

    old_value = matched_kr.current_value or 0
    matched_kr.current_value = old_value + 1

    if matched_kr.target_value and matched_kr.current_value >= matched_kr.target_value:
        matched_kr.status = "completed"

    pct = int((matched_kr.current_value / matched_kr.target_value * 100)) if matched_kr.target_value else 0
    progress_bar = "█" * (pct // 10) + "░" * (10 - pct // 10)

    msg = (
        f"💪 KR aktualisiert!\n"
        f"*{matched_kr.title}*\n"
        f"{int(old_value)} → *{int(matched_kr.current_value)}*"
        + (f"/{int(matched_kr.target_value)}" if matched_kr.target_value else "")
        + f"\n[{progress_bar}] {pct}%"
    )
    if matched_kr.status == "completed":
        msg += "\n🎉 *Ziel erreicht!*"

    logger.info(
        "Fitness KR sync: user %d, KR '%s' updated %s→%s",
        user.id, matched_kr.title, old_value, matched_kr.current_value,
    )
    return msg
