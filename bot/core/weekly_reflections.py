"""Phase 3: Weekly reflection session management.
Guides user through 5 reflection questions every Sunday evening.
"""
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import WeeklyReflection


async def start_reflection(session: AsyncSession, user_id: int) -> WeeklyReflection:
    """Start a new weekly reflection session for the current week.

    Phase 3: Creates a WeeklyReflection record, sets status='in_progress',
    sends first question. Calculates week_start (Monday) and week_number.
    """
    raise NotImplementedError("Phase 3")


async def save_answer(
    session: AsyncSession,
    reflection_id: int,
    question_num: int,
    answer: str,
) -> WeeklyReflection:
    """Save user's answer to a reflection question and advance to next.

    Phase 3: Stores answer in raw_answers, increments current_question.
    Maps answers to biggest_win, biggest_blocker, key_learning fields.
    After question 5: calls complete_reflection().
    """
    raise NotImplementedError("Phase 3")


async def get_active_reflection(session: AsyncSession, user_id: int) -> Optional[WeeklyReflection]:
    """Get the in-progress reflection for a user, if any.

    Phase 3: Returns WeeklyReflection with status='in_progress', or None.
    """
    raise NotImplementedError("Phase 3")


async def complete_reflection(session: AsyncSession, reflection_id: int) -> WeeklyReflection:
    """Mark a reflection as completed and extract insights.

    Phase 3: Sets status='completed', extracts UserInsights from answers,
    suggests priorities for next week.
    """
    raise NotImplementedError("Phase 3")


async def get_week_stats(session: AsyncSession, user_id: int) -> dict:
    """Get statistics for the current week to include in reflection.

    Phase 3: Returns dict with tasks_done, routines_completed, workouts,
    water_average, mood_average, okr_progress for the current week.
    """
    raise NotImplementedError("Phase 3")
