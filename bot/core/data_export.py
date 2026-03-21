"""Privacy-first data export — GDPR-compliant data export for Personal OS.

Provides full data export in JSON format covering all user data:
objectives, tasks, routines, logs, calendar, finance, contacts, nutrition, etc.
"""
import json
import logging
from datetime import date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from bot.database.models import (
    Budget,
    BrainDump,
    CalendarEvent,
    Commitment,
    Contact,
    DailyBrief,
    DailyContext,
    EveningCheckin,
    FinancialTransaction,
    FitnessSplit,
    GoalAdjustment,
    Interaction,
    KeyResult,
    LearningItem,
    LifeProfile,
    Log,
    NutrientTarget,
    NutritionEntry,
    Objective,
    Prediction,
    QuarterlyReview,
    Routine,
    RoutineCompletion,
    ScheduledReminder,
    ShoppingDefault,
    Task,
    User,
    UserDocument,
    UserInsight,
    WeeklyPriority,
    WeeklyReflection,
    WorkoutLog,
)

logger = logging.getLogger(__name__)


def _serialize(obj: Any) -> Any:
    """JSON-safe serializer for dates, datetimes, etc."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, date):
        return obj.isoformat()
    if hasattr(obj, "__dict__"):
        return str(obj)
    return obj


def _row_to_dict(row: Any, exclude: set[str] | None = None) -> dict:
    """Convert SQLAlchemy row to dict, excluding internal attrs."""
    exclude = exclude or set()
    exclude |= {"_sa_instance_state", "user", "registry", "metadata"}
    result = {}
    for key in row.__dict__:
        if key.startswith("_") or key in exclude:
            continue
        val = getattr(row, key)
        if isinstance(val, (list, dict)):
            result[key] = val
        elif isinstance(val, (datetime, date)):
            result[key] = val.isoformat()
        else:
            result[key] = val
    return result


async def export_user_data(session: AsyncSession, user_id: int) -> dict:
    """Export ALL user data as a structured dict (GDPR Article 20).

    Returns a comprehensive JSON-serializable dict with all user data.
    """
    logger.info("Starting data export for user %d", user_id)

    # Load user
    user_result = await session.execute(
        select(User).where(User.id == user_id)
    )
    user = user_result.scalar_one_or_none()
    if not user:
        raise ValueError(f"User {user_id} not found")

    export: dict[str, Any] = {
        "export_version": "2.0",
        "exported_at": datetime.utcnow().isoformat(),
        "user": {
            "id": user.id,
            "telegram_id": user.telegram_id,
            "telegram_username": user.telegram_username,
            "first_name": user.first_name,
            "timezone": user.timezone,
            "settings": user.settings,
            "xp": user.xp,
            "level": user.level,
            "created_at": user.created_at.isoformat() if user.created_at else None,
        },
    }

    # ─── Objectives + Key Results ─────────────────────────────────────────
    objs = (await session.execute(
        select(Objective)
        .options(selectinload(Objective.key_results))
        .where(Objective.user_id == user_id)
    )).scalars().all()
    export["objectives"] = []
    for obj in objs:
        obj_dict = _row_to_dict(obj, exclude={"key_results", "brain_dumps", "weekly_priorities", "parent_objective", "sub_objectives", "tasks", "routine_impacts"})
        obj_dict["key_results"] = [_row_to_dict(kr, exclude={"objective", "tasks", "logs", "routines", "scheduled_reminders", "weekly_priorities"}) for kr in obj.key_results]
        export["objectives"].append(obj_dict)

    # ─── Tasks ────────────────────────────────────────────────────────────
    tasks = (await session.execute(
        select(Task).where(Task.user_id == user_id)
    )).scalars().all()
    export["tasks"] = [_row_to_dict(t, exclude={"objective", "key_result", "parent_task", "sub_tasks", "blocked_by", "logs", "calendar_events", "scheduled_reminders", "weekly_priorities"}) for t in tasks]

    # ─── Routines + Completions ───────────────────────────────────────────
    routines = (await session.execute(
        select(Routine).where(Routine.user_id == user_id)
    )).scalars().all()
    export["routines"] = [_row_to_dict(r, exclude={"completions", "linked_key_result", "calendar_events", "scheduled_reminders", "objective_impacts"}) for r in routines]

    completions = (await session.execute(
        select(RoutineCompletion).where(RoutineCompletion.user_id == user_id)
    )).scalars().all()
    export["routine_completions"] = [_row_to_dict(c, exclude={"routine"}) for c in completions]

    # ─── Logs ─────────────────────────────────────────────────────────────
    logs = (await session.execute(
        select(Log).where(Log.user_id == user_id)
    )).scalars().all()
    export["logs"] = [_row_to_dict(l, exclude={"key_result", "task"}) for l in logs]

    # ─── Calendar Events ──────────────────────────────────────────────────
    events = (await session.execute(
        select(CalendarEvent).where(CalendarEvent.user_id == user_id)
    )).scalars().all()
    export["calendar_events"] = [_row_to_dict(e, exclude={"linked_task", "linked_routine"}) for e in events]

    # ─── Financial ────────────────────────────────────────────────────────
    txns = (await session.execute(
        select(FinancialTransaction).where(FinancialTransaction.user_id == user_id)
    )).scalars().all()
    export["financial_transactions"] = [_row_to_dict(t) for t in txns]

    budgets = (await session.execute(
        select(Budget).where(Budget.user_id == user_id)
    )).scalars().all()
    export["budgets"] = [_row_to_dict(b) for b in budgets]

    # ─── Contacts + Interactions + Commitments ────────────────────────────
    contacts = (await session.execute(
        select(Contact).where(Contact.user_id == user_id)
    )).scalars().all()
    export["contacts"] = [_row_to_dict(c, exclude={"interactions", "commitments"}) for c in contacts]

    interactions = (await session.execute(
        select(Interaction).where(Interaction.user_id == user_id)
    )).scalars().all()
    export["interactions"] = [_row_to_dict(i, exclude={"contact"}) for i in interactions]

    commitments = (await session.execute(
        select(Commitment).where(Commitment.user_id == user_id)
    )).scalars().all()
    export["commitments"] = [_row_to_dict(c, exclude={"contact"}) for c in commitments]

    # ─── Nutrition ────────────────────────────────────────────────────────
    entries = (await session.execute(
        select(NutritionEntry).where(NutritionEntry.user_id == user_id)
    )).scalars().all()
    export["nutrition_entries"] = [_row_to_dict(e) for e in entries]

    targets = (await session.execute(
        select(NutrientTarget).where(NutrientTarget.user_id == user_id)
    )).scalars().all()
    export["nutrient_targets"] = [_row_to_dict(t) for t in targets]

    # ─── Fitness ──────────────────────────────────────────────────────────
    workouts = (await session.execute(
        select(WorkoutLog).where(WorkoutLog.user_id == user_id)
    )).scalars().all()
    export["workout_logs"] = [_row_to_dict(w) for w in workouts]

    splits = (await session.execute(
        select(FitnessSplit).where(FitnessSplit.user_id == user_id)
    )).scalars().all()
    export["fitness_splits"] = [_row_to_dict(s) for s in splits]

    # ─── Documents + Brain Dumps ──────────────────────────────────────────
    docs = (await session.execute(
        select(UserDocument).where(UserDocument.user_id == user_id)
    )).scalars().all()
    export["documents"] = [_row_to_dict(d) for d in docs]

    dumps = (await session.execute(
        select(BrainDump).where(BrainDump.user_id == user_id)
    )).scalars().all()
    export["brain_dumps"] = [_row_to_dict(d, exclude={"linked_objective"}) for d in dumps]

    # ─── Reflections + Insights ───────────────────────────────────────────
    reflections = (await session.execute(
        select(WeeklyReflection).where(WeeklyReflection.user_id == user_id)
    )).scalars().all()
    export["weekly_reflections"] = [_row_to_dict(r) for r in reflections]

    insights = (await session.execute(
        select(UserInsight).where(UserInsight.user_id == user_id)
    )).scalars().all()
    export["insights"] = [_row_to_dict(i) for i in insights]

    # ─── Predictions + Adjustments ────────────────────────────────────────
    predictions = (await session.execute(
        select(Prediction).where(Prediction.user_id == user_id)
    )).scalars().all()
    export["predictions"] = [_row_to_dict(p) for p in predictions]

    adjustments = (await session.execute(
        select(GoalAdjustment).where(GoalAdjustment.user_id == user_id)
    )).scalars().all()
    export["goal_adjustments"] = [_row_to_dict(a) for a in adjustments]

    # ─── Life Profile ─────────────────────────────────────────────────────
    profile = (await session.execute(
        select(LifeProfile).where(LifeProfile.user_id == user_id)
    )).scalar_one_or_none()
    export["life_profile"] = _row_to_dict(profile) if profile else None

    # ─── Quarterly Reviews ────────────────────────────────────────────────
    reviews = (await session.execute(
        select(QuarterlyReview).where(QuarterlyReview.user_id == user_id)
    )).scalars().all()
    export["quarterly_reviews"] = [_row_to_dict(r) for r in reviews]

    # ─── Learning ─────────────────────────────────────────────────────────
    items = (await session.execute(
        select(LearningItem).where(LearningItem.user_id == user_id)
    )).scalars().all()
    export["learning_items"] = [_row_to_dict(i, exclude={"reviews"}) for i in items]

    # ─── Daily Intelligence ───────────────────────────────────────────────
    contexts = (await session.execute(
        select(DailyContext).where(DailyContext.user_id == user_id)
    )).scalars().all()
    export["daily_contexts"] = [_row_to_dict(c) for c in contexts]

    checkins = (await session.execute(
        select(EveningCheckin).where(EveningCheckin.user_id == user_id)
    )).scalars().all()
    export["evening_checkins"] = [_row_to_dict(c) for c in checkins]

    # ─── Shopping Defaults ────────────────────────────────────────────────
    defaults = (await session.execute(
        select(ShoppingDefault).where(ShoppingDefault.user_id == user_id)
    )).scalars().all()
    export["shopping_defaults"] = [_row_to_dict(d) for d in defaults]

    logger.info("Data export completed for user %d: %d sections", user_id, len(export))
    return export


def export_to_json(data: dict) -> str:
    """Serialize export data to JSON string."""
    return json.dumps(data, default=_serialize, ensure_ascii=False, indent=2)


async def delete_user_data(session: AsyncSession, user_id: int) -> dict:
    """Delete all user data (GDPR Article 17 — Right to Erasure).

    Returns summary of deleted records per table.
    """
    logger.warning("GDPR deletion requested for user %d", user_id)

    user_result = await session.execute(
        select(User).where(User.id == user_id)
    )
    user = user_result.scalar_one_or_none()
    if not user:
        raise ValueError(f"User {user_id} not found")

    # CASCADE delete handles all related tables
    await session.delete(user)
    await session.flush()

    logger.warning("GDPR deletion completed for user %d", user_id)
    return {
        "user_id": user_id,
        "deleted": True,
        "message": "Alle Nutzerdaten wurden unwiderruflich gelöscht.",
    }
