"""Phase 8.1: Weekly reflection — starts structured 7-question session every Sunday."""
import logging
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from openai import AsyncOpenAI
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import settings
from bot.core.weekly_reflections import get_week_stats, start_reflection
from bot.database.connection import get_session
from bot.database.models import User, WeeklyReflection
from bot.telegram.sender import send_message

logger = logging.getLogger(__name__)
openai_client = AsyncOpenAI(api_key=settings.openai_api_key)


async def check_and_trigger_reflections() -> None:
    """
    Runs every minute. On Sundays, checks each user's reflection time.
    Sends a GPT-4o-generated weekly summary with reflection questions.
    """
    now_berlin = datetime.now(tz=ZoneInfo("Europe/Berlin"))
    today = now_berlin.date()

    # Only run on Sundays
    if today.weekday() != 6:
        return

    current_time = now_berlin.strftime("%H:%M")

    async with get_session() as session:
        result = await session.execute(
            select(User).where(User.is_active == True)  # noqa: E712
        )
        users = result.scalars().all()

        for user in users:
            s = user.settings or {}
            if not s.get("reflection_enabled", True):
                continue

            reflection_time = s.get("weekly_reflection_time", "19:00")
            if current_time != reflection_time:
                continue

            # Calculate week start (last Monday)
            week_start = today - timedelta(days=today.weekday())
            week_number = today.isocalendar()[1]
            year = today.year

            # Check if already sent this week
            existing = await session.execute(
                select(WeeklyReflection).where(and_(
                    WeeklyReflection.user_id == user.id,
                    WeeklyReflection.week_start == week_start,
                ))
            )
            if existing.scalar_one_or_none():
                continue

            try:
                # Generate intro with week stats
                stats = await get_week_stats(session, user.id)
                intro = await _generate_intro(user, stats, week_start, today)

                # Create reflection session and get Q1
                _, q1_text = await start_reflection(session, user.id)
                full_text = intro + "\n\n" + q1_text

                success = await send_message(user.telegram_id, full_text)
                if success:
                    logger.info("Weekly reflection started for user %s", user.id)
                    # Check achievements
                    try:
                        from bot.core.achievements import check_achievements, format_achievement_message
                        from bot.core.gamification import add_xp
                        newly_unlocked = await check_achievements(user.id, session)
                        for achievement in newly_unlocked:
                            await send_message(user.telegram_id, format_achievement_message(achievement))
                            if achievement.xp_reward > 0:
                                _, new_level, leveled_up, _ = await add_xp(
                                    user.id, achievement.xp_reward, f"achievement_{achievement.key}", session
                                )
                                if leveled_up:
                                    await send_message(
                                        user.telegram_id,
                                        f"⬆️ LEVEL UP! Du bist jetzt Level {new_level}! 🎉",
                                    )
                    except Exception:
                        logger.warning("Achievement check failed after reflection trigger for user %s", user.id)
            except Exception:
                logger.exception("Failed to send weekly reflection to user %s", user.id)


async def _generate_intro(user: User, stats: dict, week_start: date, week_end: date) -> str:
    """Generate a short GPT-4o intro summarising the week before Q1."""
    week_str = f"KW{week_start.isocalendar()[1]} ({week_start.strftime('%d.%m.')} – {week_end.strftime('%d.%m.%Y')})"
    name = user.first_name or "Chef"

    mood_line = f"Stimmung Ø {stats['mood_avg']}/10" if stats.get("mood_avg") else ""
    context = (
        f"Tasks erledigt: {stats['tasks_done']}, "
        f"Workout-Tage: {stats['workout_days']}, "
        f"Routinen: {stats['routine_rate']}%"
        + (f", {mood_line}" if mood_line else "")
    )

    prompt = (
        f"Du bist der persönliche COO von {name}. Sonntag Abend — Wochen-Reflexion {week_str}.\n\n"
        f"Wochendaten: {context}\n\n"
        "Schreib eine kurze, persönliche Begrüßung (2-3 Sätze) mit Wochenüberblick und den "
        "Key-Stats. Motivierend und ehrlich. KEIN Fragenstellen — das folgt separat. Max 80 Wörter."
    )

    try:
        response = await openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200,
            temperature=0.8,
        )
        intro = response.choices[0].message.content or ""
    except Exception:
        intro = ""

    if not intro:
        intro = (
            f"🔮 *Wochen-Reflexion {week_str}*\n\n"
            f"Hey {name}! 📊 Diese Woche: {stats['tasks_done']} Tasks ✅ · "
            f"{stats['workout_days']} Workouts 💪 · {stats['routine_rate']}% Routinen 🔄"
        )

    return intro


async def send_reflection_invitation(user_id: int) -> None:
    """Kept for compatibility. The main logic is now in check_and_trigger_reflections."""
    logger.info("send_reflection_invitation called for user %s", user_id)
