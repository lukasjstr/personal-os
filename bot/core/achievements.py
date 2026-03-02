"""Achievement engine — checks and unlocks achievements for a user."""
import logging
from datetime import date, datetime, timedelta

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import (
    Achievement,
    BrainDump,
    KeyResult,
    Log,
    Objective,
    Task,
    UserAchievement,
    WeeklyReflection,
)

logger = logging.getLogger(__name__)


async def _get_streak(session: AsyncSession, user_id: int) -> int:
    """Calculate current consecutive-day streak based on log activity (up to 120 days)."""
    since = datetime.combine(date.today() - timedelta(days=120), datetime.min.time())
    result = await session.execute(
        select(Log.logged_at).where(and_(Log.user_id == user_id, Log.logged_at >= since))
    )
    active_dates = {dt.date() for dt in result.scalars().all()}

    streak = 0
    check_date = date.today()
    while check_date in active_dates:
        streak += 1
        check_date -= timedelta(days=1)
    return streak


async def _check_condition(
    key: str,
    condition_type: str,
    condition_value: int,
    session: AsyncSession,
    user_id: int,
) -> bool:
    """Return True if the achievement condition is met."""
    try:
        if condition_type == "streak":
            streak = await _get_streak(session, user_id)
            return streak >= condition_value

        elif condition_type == "count":
            if key == "macher" or key == "hundertschaft":
                # Count completed tasks
                result = await session.execute(
                    select(func.count()).select_from(Task).where(
                        and_(Task.user_id == user_id, Task.status == "done")
                    )
                )
                count = result.scalar() or 0
                return count >= condition_value

            elif key == "zielstrebig":
                result = await session.execute(
                    select(func.count()).select_from(Objective).where(
                        Objective.user_id == user_id
                    )
                )
                count = result.scalar() or 0
                return count >= condition_value

            elif key == "selbstreflektiert":
                # Count reflections that were at least started (in_progress or completed)
                result = await session.execute(
                    select(func.count()).select_from(WeeklyReflection).where(
                        and_(
                            WeeklyReflection.user_id == user_id,
                            WeeklyReflection.status.in_(["in_progress", "completed"]),
                        )
                    )
                )
                count = result.scalar() or 0
                return count >= condition_value

            elif key == "hydration_hero":
                # Total liters across all time (condition_value=100 means 100L)
                result = await session.execute(
                    select(Log).where(
                        and_(Log.user_id == user_id, Log.log_type == "water")
                    )
                )
                logs = result.scalars().all()
                total = sum(l.data.get("amount", 0) for l in logs)
                return total >= condition_value

            elif key == "brain_dumper":
                result = await session.execute(
                    select(func.count()).select_from(BrainDump).where(
                        BrainDump.user_id == user_id
                    )
                )
                count = result.scalar() or 0
                return count >= condition_value

            elif key == "gym_rat":
                # Count distinct workout log days or total workout logs
                result = await session.execute(
                    select(func.count()).select_from(Log).where(
                        and_(Log.user_id == user_id, Log.log_type == "workout")
                    )
                )
                count = result.scalar() or 0
                return count >= condition_value

        elif condition_type == "milestone":
            if key == "erster_schritt":
                # True once user has at least one task or objective
                result = await session.execute(
                    select(func.count()).select_from(Task).where(
                        Task.user_id == user_id
                    )
                )
                return (result.scalar() or 0) > 0

            elif key == "kr_knacker":
                # Any key result completed (100%)
                result = await session.execute(
                    select(func.count()).select_from(KeyResult).where(
                        and_(
                            KeyResult.user_id == user_id,
                            KeyResult.status == "completed",
                        )
                    )
                )
                return (result.scalar() or 0) >= 1

            elif key == "perfekte_woche":
                # Any week where routine completion rate was 100% — simplified:
                # Check if user has had 7 consecutive days with log activity in the last 60 days
                since = datetime.combine(date.today() - timedelta(days=60), datetime.min.time())
                result = await session.execute(
                    select(Log.logged_at).where(
                        and_(Log.user_id == user_id, Log.logged_at >= since)
                    )
                )
                active_dates = {dt.date() for dt in result.scalars().all()}
                # Check any 7-day window with all days active
                check = date.today() - timedelta(days=60)
                while check <= date.today() - timedelta(days=6):
                    week = {check + timedelta(days=i) for i in range(7)}
                    if week.issubset(active_dates):
                        return True
                    check += timedelta(days=1)
                return False

            elif key == "comeback_kid":
                # User had a gap of ≥7 days and then came back
                since = datetime.combine(date.today() - timedelta(days=180), datetime.min.time())
                result = await session.execute(
                    select(Log.logged_at).where(
                        and_(Log.user_id == user_id, Log.logged_at >= since)
                    )
                )
                active_dates = sorted({dt.date() for dt in result.scalars().all()})
                if len(active_dates) < 2:
                    return False
                for i in range(1, len(active_dates)):
                    gap = (active_dates[i] - active_dates[i - 1]).days
                    if gap >= 7:
                        return True
                return False

    except Exception as e:
        logger.warning("Achievement condition check failed for %s: %s", key, e)

    return False


async def check_achievements(
    user_id: int,
    session: AsyncSession,
) -> list[Achievement]:
    """Check all achievement conditions and unlock new ones.

    Returns list of newly unlocked Achievement objects.
    """
    # Load all achievements not yet unlocked by this user
    unlocked_result = await session.execute(
        select(UserAchievement.achievement_id).where(
            UserAchievement.user_id == user_id
        )
    )
    already_unlocked_ids = set(unlocked_result.scalars().all())

    all_result = await session.execute(select(Achievement))
    all_achievements = all_result.scalars().all()

    newly_unlocked: list[Achievement] = []

    for achievement in all_achievements:
        if achievement.id in already_unlocked_ids:
            continue

        met = await _check_condition(
            achievement.key,
            achievement.condition_type,
            achievement.condition_value,
            session,
            user_id,
        )

        if met:
            ua = UserAchievement(
                user_id=user_id,
                achievement_id=achievement.id,
            )
            session.add(ua)
            newly_unlocked.append(achievement)
            logger.info(
                "Achievement unlocked for user %s: %s (%s)",
                user_id, achievement.key, achievement.title,
            )

    if newly_unlocked:
        await session.flush()

    return newly_unlocked


def format_achievement_message(achievement: Achievement) -> str:
    """Format a Telegram notification message for a newly unlocked achievement."""
    return (
        f"🏆 ACHIEVEMENT UNLOCKED!\n"
        f"{achievement.emoji} {achievement.title}\n"
        f"{achievement.description}\n"
        f"+{achievement.xp_reward} XP!"
    )
