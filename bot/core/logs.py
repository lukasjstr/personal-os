"""Log creation for all log types (workout, water, mood, progress, food, etc.)."""
from datetime import datetime, date
from typing import Any, Optional

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import KeyResult, Log


async def _create_log(
    session: AsyncSession,
    user_id: int,
    log_type: str,
    data: dict[str, Any],
    raw_input: Optional[str] = None,
    source: str = "text",
    key_result_id: Optional[int] = None,
    task_id: Optional[int] = None,
) -> Log:
    log = Log(
        user_id=user_id,
        log_type=log_type,
        data=data,
        raw_input=raw_input,
        source=source,
        key_result_id=key_result_id,
        task_id=task_id,
        logged_at=datetime.utcnow(),
    )
    session.add(log)
    await session.flush()
    return log


async def log_workout(
    session: AsyncSession,
    user_id: int,
    exercise: str,
    weight: Optional[float] = None,
    reps: Optional[int] = None,
    sets: Optional[int] = None,
    duration_minutes: Optional[int] = None,
    notes: Optional[str] = None,
    key_result_id: Optional[int] = None,
) -> Log:
    """Log a workout entry."""
    data: dict[str, Any] = {"exercise": exercise}
    if weight is not None:
        data["weight"] = weight
    if reps is not None:
        data["reps"] = reps
    if sets is not None:
        data["sets"] = sets
    if duration_minutes is not None:
        data["duration_minutes"] = duration_minutes
    if notes:
        data["notes"] = notes

    raw = f"{exercise}"
    if weight:
        raw += f" {weight}kg"
    if reps and sets:
        raw += f" ×{reps}×{sets}"

    return await _create_log(
        session, user_id, "workout", data,
        raw_input=raw, key_result_id=key_result_id,
    )


async def log_water(
    session: AsyncSession,
    user_id: int,
    amount_liters: float,
) -> float:
    """Log water intake and return today's total in liters."""
    await _create_log(
        session, user_id, "water",
        {"amount": amount_liters},
        raw_input=f"{amount_liters}L Wasser",
    )

    today_start = datetime.combine(date.today(), datetime.min.time())
    result = await session.execute(
        select(Log).where(
            and_(
                Log.user_id == user_id,
                Log.log_type == "water",
                Log.logged_at >= today_start,
            )
        )
    )
    today_logs = result.scalars().all()
    return sum(l.data.get("amount", 0) for l in today_logs)


async def log_mood(
    session: AsyncSession,
    user_id: int,
    score: int,
    notes: str = "",
) -> Log:
    """Log mood / day rating."""
    return await _create_log(
        session, user_id, "mood",
        {"score": score, "notes": notes},
        raw_input=f"Mood: {score}/10 — {notes}",
    )


async def log_progress(
    session: AsyncSession,
    user_id: int,
    key_result_id: int,
    value: float,
    increment: bool = True,
    notes: str = "",
) -> Log:
    """Log progress for a key result and update its current value.
    If increment=True, value is added to current. If False, value replaces current.
    """
    kr_result = await session.execute(
        select(KeyResult).where(KeyResult.id == key_result_id)
    )
    kr = kr_result.scalar_one_or_none()
    if kr:
        if increment:
            kr.current_value = (kr.current_value or 0) + value
        else:
            kr.current_value = value
        # Auto-complete if target reached
        if kr.target_value and kr.current_value >= kr.target_value:
            kr.status = "completed"
        await session.flush()

    return await _create_log(
        session, user_id, "progress",
        {"value": value, "increment": increment, "description": notes, "key_result_id": key_result_id},
        raw_input=f"Fortschritt {'+'if increment else '='}{value} für KR#{key_result_id}",
        key_result_id=key_result_id,
    )


async def log_food(
    session: AsyncSession,
    user_id: int,
    description: str,
    calories: Optional[int] = None,
    meal_type: Optional[str] = None,
    notes: Optional[str] = None,
) -> Log:
    """Log a meal or food entry."""
    data: dict[str, Any] = {"description": description}
    if calories is not None:
        data["calories"] = calories
    if meal_type:
        data["meal_type"] = meal_type
    if notes:
        data["notes"] = notes

    return await _create_log(
        session, user_id, "food",
        data,
        raw_input=f"{meal_type or 'Mahlzeit'}: {description}",
    )


async def log_general(
    session: AsyncSession,
    user_id: int,
    content: str,
    source: str = "text",
) -> Log:
    """Log a general note."""
    return await _create_log(
        session, user_id, "note",
        {"content": content},
        raw_input=content,
        source=source,
    )


async def get_recent_logs(session: AsyncSession, user_id: int, limit: int = 10) -> list[Log]:
    """Get most recent logs for a user."""
    result = await session.execute(
        select(Log)
        .where(Log.user_id == user_id)
        .order_by(Log.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_mood_trend(session: AsyncSession, user_id: int, days: int = 7) -> list[int]:
    """Get mood scores for the last N days."""
    from datetime import timedelta
    since = datetime.utcnow() - timedelta(days=days)
    result = await session.execute(
        select(Log)
        .where(and_(
            Log.user_id == user_id,
            Log.log_type == "mood",
            Log.logged_at >= since,
        ))
        .order_by(Log.logged_at.asc())
    )
    logs = result.scalars().all()
    return [l.data.get("score", 0) for l in logs if l.data.get("score")]
