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
    """Get fitness plan with last session weights and progressive overload suggestions."""
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

    # Build per-exercise history: exercise_name → {date, weight, reps, sets}
    exercise_history: dict[str, dict] = {}
    all_workout_logs_result = await session.execute(
        select(Log)
        .where(and_(Log.user_id == user_id, Log.log_type == "workout"))
        .order_by(Log.logged_at.desc())
        .limit(100)
    )
    for wl in all_workout_logs_result.scalars().all():
        ex = (wl.data.get("exercise") or "").lower()
        if ex and ex not in exercise_history:
            exercise_history[ex] = {
                "date": wl.logged_at.date(),
                "weight": wl.data.get("weight"),
                "reps": wl.data.get("reps"),
                "sets": wl.data.get("sets"),
            }

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
            ex_name = ex.get("name", "?")
            ex_lower = ex_name.lower()

            # Check history for this exercise
            hist = None
            for hist_key, hist_val in exercise_history.items():
                if hist_key in ex_lower or ex_lower in hist_key:
                    hist = hist_val
                    break

            sets_reps = ""
            if ex.get("sets") and ex.get("reps"):
                sets_reps = f" {ex['sets']}×{ex['reps']}"
            elif ex.get("sets"):
                sets_reps = f" {ex['sets']} Sätze"

            if hist and hist.get("weight"):
                last_w = hist["weight"]
                next_w = round(last_w + 2.5, 1)
                last_date = hist["date"].strftime("%d.%m") if hist.get("date") else "?"
                last_reps_str = f" ×{hist['sets']}×{hist['reps']}" if hist.get("sets") and hist.get("reps") else ""
                weight_str = f" | zuletzt: {last_w}kg{last_reps_str} ({last_date}) → heute: *{next_w}kg*"
                lines.append(f"  ☐ {ex_name}{sets_reps}{weight_str}")
            elif ex.get("target_weight"):
                lines.append(f"  ☐ {ex_name}{sets_reps} @ {ex['target_weight']}kg")
            else:
                lines.append(f"  ☐ {ex_name}{sets_reps}")

    return "\n".join(lines)
