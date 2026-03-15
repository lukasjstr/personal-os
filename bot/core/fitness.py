"""Fitness split management — create, query, and recommend splits."""
from datetime import datetime, timedelta
from typing import Any, Optional

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.core.fitness_protocol import format_split_text, get_today_split, load_fitness_protocol
from bot.database.models import FitnessSplit, Log

DAYS_DE = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]


async def create_fitness_split(
    session: AsyncSession,
    user_id: int,
    name: str,
    exercises: list[dict[str, Any]],
    day_of_week: Optional[int] = None,
    order_in_rotation: Optional[int] = None,
) -> FitnessSplit:
    """Create a new fitness split."""
    split = FitnessSplit(
        user_id=user_id,
        name=name,
        exercises=exercises,
        day_of_week=day_of_week,
        order_in_rotation=order_in_rotation,
    )
    session.add(split)
    await session.flush()
    return split


async def get_fitness_plan(session: AsyncSession, user_id: int) -> str:
    """Get all fitness splits and recommend the next one based on last workouts."""
    result = await session.execute(
        select(FitnessSplit)
        .where(FitnessSplit.user_id == user_id)
        .order_by(FitnessSplit.order_in_rotation.nulls_last(), FitnessSplit.created_at)
    )
    splits = result.scalars().all()

    if not splits:
        try:
            protocol = load_fitness_protocol()
            today_view = get_today_split(protocol)
            fallback = [
                "Noch keine individuellen Fitness-Splits in der DB definiert.",
                "Ich nutze deinen hinterlegten 3er-Split aus dem Protocol:",
                format_split_text(today_view),
            ]
            return "\n".join(fallback)
        except Exception:
            return (
                "Noch keine Fitness-Splits definiert. "
                "Erstelle z.B. einen Push/Pull/Leg-Split mit create_fitness_split."
            )

    # Determine last used split from recent workout logs
    since = datetime.utcnow() - timedelta(days=14)
    log_result = await session.execute(
        select(Log)
        .where(and_(
            Log.user_id == user_id,
            Log.log_type == "workout",
            Log.logged_at >= since,
        ))
        .order_by(Log.logged_at.desc())
    )
    recent_logs = log_result.scalars().all()

    last_split_id = None
    for log in recent_logs:
        if log.data.get("split_id"):
            last_split_id = log.data["split_id"]
            break

    # Determine next split in rotation
    split_ids = [s.id for s in splits]
    next_split = None
    if split_ids:
        if last_split_id and last_split_id in split_ids:
            idx = split_ids.index(last_split_id)
            next_split = splits[(idx + 1) % len(splits)]
        else:
            # Check if a split is assigned to today's weekday
            today_dow = datetime.utcnow().weekday()
            for s in splits:
                if s.day_of_week == today_dow:
                    next_split = s
                    break
            if not next_split:
                next_split = splits[0]

    lines = ["🏋️ *Dein Fitness-Plan:*\n"]
    for s in splits:
        day_str = f" ({DAYS_DE[s.day_of_week]})" if s.day_of_week is not None else ""
        order_str = f"{s.order_in_rotation}. " if s.order_in_rotation else ""
        exercises_preview = ", ".join(e.get("name", "?") for e in (s.exercises or [])[:4])
        if len(s.exercises or []) > 4:
            exercises_preview += f" +{len(s.exercises) - 4}"
        marker = " ← **HEUTE**" if next_split and s.id == next_split.id else ""
        lines.append(f"{order_str}*{s.name}*{day_str}: {exercises_preview}{marker}")

    if next_split:
        lines.append(f"\n💪 *Nächstes Workout: {next_split.name}*")
        for ex in next_split.exercises or []:
            sets_reps = ""
            if ex.get("sets") and ex.get("reps"):
                sets_reps = f" {ex['sets']}×{ex['reps']}"
            elif ex.get("sets"):
                sets_reps = f" {ex['sets']} Sätze"
            weight = f" @ {ex['target_weight']}kg" if ex.get("target_weight") else ""
            lines.append(f"  ☐ {ex.get('name', '?')}{sets_reps}{weight}")

    return "\n".join(lines)
