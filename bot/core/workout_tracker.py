"""Workout weight tracking: parse input, log to WorkoutLog, auto-progression."""
from __future__ import annotations

import re
from datetime import date, datetime
from typing import Optional

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import User, WorkoutLog

# Pattern: "Beinpresse 80kg 3x10" or "Bankdrücken 100 kg 4x8"
_WORKOUT_RE = re.compile(
    r"^(?P<exercise>[A-Za-zÄÖÜäöüß\s\-\/]+?)"
    r"\s+(?P<weight>\d+(?:[.,]\d+)?)\s*kg"
    r"\s+(?P<sets>\d+)[xX×](?P<reps>\d+)"
    r"\s*$",
    re.IGNORECASE,
)

# Pattern: "Welches Gewicht Beinpresse?" or "welches gewicht beinpresse"
_WEIGHT_QUERY_RE = re.compile(
    r"^welches\s+gewicht\s+(?P<exercise>.+?)[\?!]?\s*$",
    re.IGNORECASE,
)

AUTO_PROGRESSION_KG = 2.5
SESSIONS_FOR_PROGRESSION = 2


def parse_workout_input(text: str) -> Optional[dict]:
    """Parse 'Beinpresse 80kg 3x10' → dict with exercise/weight_kg/sets/reps.
    Returns None if text doesn't match the workout pattern.
    """
    m = _WORKOUT_RE.match(text.strip())
    if not m:
        return None
    return {
        "exercise": m.group("exercise").strip(),
        "weight_kg": float(m.group("weight").replace(",", ".")),
        "sets": int(m.group("sets")),
        "reps": int(m.group("reps")),
    }


def parse_weight_query(text: str) -> Optional[str]:
    """Parse 'Welches Gewicht Beinpresse?' → exercise name. Returns None if no match."""
    m = _WEIGHT_QUERY_RE.match(text.strip())
    return m.group("exercise").strip() if m else None


async def log_workout_entry(
    session: AsyncSession,
    user_id: int,
    exercise: str,
    weight_kg: float,
    sets: int,
    reps: int,
    logged_date: Optional[date] = None,
) -> WorkoutLog:
    """Save a workout entry to workout_logs."""
    entry = WorkoutLog(
        user_id=user_id,
        exercise=exercise,
        weight_kg=weight_kg,
        sets=sets,
        reps=reps,
        logged_date=logged_date or date.today(),
    )
    session.add(entry)
    await session.flush()
    return entry


async def get_last_weight(
    session: AsyncSession,
    user_id: int,
    exercise: str,
) -> Optional[WorkoutLog]:
    """Return the most recent WorkoutLog for this exercise."""
    exercise_lower = exercise.lower()
    result = await session.execute(
        select(WorkoutLog)
        .where(
            and_(
                WorkoutLog.user_id == user_id,
                WorkoutLog.exercise.ilike(f"%{exercise_lower}%"),
            )
        )
        .order_by(WorkoutLog.logged_date.desc(), WorkoutLog.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_progression_suggestion(
    session: AsyncSession,
    user_id: int,
    exercise: str,
) -> dict:
    """Return last weight + progression suggestion for an exercise.

    Suggests +2.5kg after SESSIONS_FOR_PROGRESSION successful sessions at same weight.
    """
    exercise_lower = exercise.lower()
    result = await session.execute(
        select(WorkoutLog)
        .where(
            and_(
                WorkoutLog.user_id == user_id,
                WorkoutLog.exercise.ilike(f"%{exercise_lower}%"),
            )
        )
        .order_by(WorkoutLog.logged_date.desc(), WorkoutLog.created_at.desc())
        .limit(SESSIONS_FOR_PROGRESSION + 2)
    )
    recent = result.scalars().all()

    if not recent:
        return {"last_weight": None, "suggested_weight": None, "progression": False}

    last = recent[0]
    last_weight = last.weight_kg

    # Check if last N sessions all used same weight → ready to progress
    progression = False
    suggested_weight = last_weight
    if len(recent) >= SESSIONS_FOR_PROGRESSION and last_weight is not None:
        same_weight_count = sum(
            1 for r in recent[:SESSIONS_FOR_PROGRESSION]
            if r.weight_kg == last_weight
        )
        if same_weight_count >= SESSIONS_FOR_PROGRESSION:
            progression = True
            suggested_weight = last_weight + AUTO_PROGRESSION_KG

    return {
        "last_weight": last_weight,
        "suggested_weight": suggested_weight,
        "progression": progression,
        "last_sets": last.sets,
        "last_reps": last.reps,
        "last_date": last.logged_date.isoformat() if last.logged_date else None,
    }


async def handle_workout_message(
    session: AsyncSession,
    user_id: int,
    text: str,
) -> Optional[str]:
    """Try to handle a workout-related message.

    Returns a reply string if handled, or None if not a workout message.
    """
    # Check for weight query first
    exercise_query = parse_weight_query(text)
    if exercise_query:
        info = await get_progression_suggestion(session, user_id, exercise_query)
        if info["last_weight"] is None:
            return f"📊 Noch kein Gewicht für *{exercise_query}* geloggt."
        last_w = info["last_weight"]
        last_date = info.get("last_date", "?")
        sets = info.get("last_sets")
        reps = info.get("last_reps")
        sets_reps = f" ({sets}×{reps})" if sets and reps else ""
        reply = f"📊 *{exercise_query}* — letztes Gewicht: *{last_w}kg*{sets_reps} ({last_date})"
        if info["progression"]:
            reply += (
                f"\n💡 Auto-Progression: Du hast {SESSIONS_FOR_PROGRESSION}× "
                f"{last_w}kg geschafft → versuche *{info['suggested_weight']}kg*! 🔥"
            )
        return reply

    # Check for workout log input
    parsed = parse_workout_input(text)
    if parsed:
        entry = await log_workout_entry(
            session,
            user_id,
            exercise=parsed["exercise"],
            weight_kg=parsed["weight_kg"],
            sets=parsed["sets"],
            reps=parsed["reps"],
        )
        reply = (
            f"💪 Geloggt: *{entry.exercise}* — "
            f"{entry.weight_kg}kg, {entry.sets}×{entry.reps}"
        )
        # Check if progression is due after this session
        info = await get_progression_suggestion(session, user_id, entry.exercise)
        if info["progression"] and info["suggested_weight"] != entry.weight_kg:
            reply += (
                f"\n💡 Beim nächsten Mal: *{info['suggested_weight']}kg* (+{AUTO_PROGRESSION_KG}kg)"
            )

        # Sync workout to fitness KR
        try:
            from bot.core.fitness_kr_sync import sync_workout_to_kr
            user_res = await session.execute(select(User).where(User.id == user_id))
            user_obj = user_res.scalar_one_or_none()
            if user_obj:
                kr_update_msg = await sync_workout_to_kr(session, user_obj, entry)
                if kr_update_msg:
                    reply = reply + "\n\n" + kr_update_msg
        except Exception:
            pass  # non-fatal

        return reply

    return None
