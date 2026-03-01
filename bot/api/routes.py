"""REST API routes for the dashboard."""
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from bot.api.auth import generate_api_token, get_current_user
from bot.core.brain_dumps import get_all_brain_dumps
from bot.core.routines import get_active_routines, get_todays_completions
from bot.core.tasks import get_open_tasks
from bot.database.connection import get_db
from bot.database.models import (
    BrainDump, CalendarEvent, KeyResult, Log, Objective, Routine,
    RoutineCompletion, Task, User,
)

router = APIRouter(prefix="/api")


@router.get("/objectives")
async def list_objectives(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Get all objectives with key results."""
    result = await session.execute(
        select(Objective)
        .options(selectinload(Objective.key_results))
        .where(Objective.user_id == user.id)
        .order_by(Objective.status, Objective.created_at)
    )
    objectives = result.scalars().all()
    return {
        "objectives": [
            {
                "id": o.id,
                "title": o.title,
                "description": o.description,
                "category": o.category,
                "status": o.status,
                "target_date": o.target_date.isoformat() if o.target_date else None,
                "created_at": o.created_at.isoformat(),
                "key_results": [
                    {
                        "id": kr.id,
                        "title": kr.title,
                        "metric_type": kr.metric_type,
                        "target_value": kr.target_value,
                        "current_value": kr.current_value,
                        "unit": kr.unit,
                        "frequency": kr.frequency,
                        "status": kr.status,
                        "progress_pct": (
                            min(100, int((kr.current_value / kr.target_value) * 100))
                            if kr.target_value and kr.target_value > 0
                            else 0
                        ),
                    }
                    for kr in o.key_results
                ],
            }
            for o in objectives
        ]
    }


@router.get("/tasks")
async def list_tasks(
    status: Optional[str] = Query(None),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Get tasks, optionally filtered by status."""
    conditions = [Task.user_id == user.id]
    if status:
        conditions.append(Task.status == status)
    else:
        conditions.append(Task.status.in_(["todo", "in_progress"]))

    result = await session.execute(
        select(Task)
        .where(and_(*conditions))
        .order_by(Task.priority.desc(), Task.due_date.asc().nulls_last())
    )
    tasks = result.scalars().all()
    return {
        "tasks": [
            {
                "id": t.id,
                "title": t.title,
                "description": t.description,
                "status": t.status,
                "priority": t.priority,
                "due_date": t.due_date.isoformat() if t.due_date else None,
                "completed_at": t.completed_at.isoformat() if t.completed_at else None,
                "key_result_id": t.key_result_id,
                "created_at": t.created_at.isoformat(),
            }
            for t in tasks
        ]
    }


@router.get("/logs")
async def list_logs(
    log_type: Optional[str] = Query(None),
    days: int = Query(30, ge=1, le=365),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Get logs filtered by type and time range."""
    since = datetime.utcnow() - timedelta(days=days)
    conditions = [Log.user_id == user.id, Log.created_at >= since]
    if log_type:
        conditions.append(Log.log_type == log_type)

    result = await session.execute(
        select(Log)
        .where(and_(*conditions))
        .order_by(Log.logged_at.desc())
        .limit(200)
    )
    logs = result.scalars().all()
    return {
        "logs": [
            {
                "id": l.id,
                "log_type": l.log_type,
                "data": l.data,
                "source": l.source,
                "raw_input": l.raw_input,
                "logged_at": l.logged_at.isoformat(),
                "key_result_id": l.key_result_id,
            }
            for l in logs
        ]
    }


@router.get("/routines")
async def list_routines(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Get routines with today's completion status."""
    routines = await get_active_routines(session, user.id)
    completed_today = await get_todays_completions(session, user.id)
    return {
        "routines": [
            {
                "id": r.id,
                "title": r.title,
                "description": r.description,
                "schedule_cron": r.schedule_cron,
                "frequency_human": r.frequency_human,
                "status": r.status,
                "completed_today": r.id in completed_today,
            }
            for r in routines
        ]
    }


@router.get("/brain-dumps")
async def list_brain_dumps(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Get all brain dumps."""
    dumps = await get_all_brain_dumps(session, user.id)
    return {
        "brain_dumps": [
            {
                "id": bd.id,
                "raw_input": bd.raw_input,
                "processed": bd.processed,
                "ai_interpretation": bd.ai_interpretation,
                "linked_objective_id": bd.linked_objective_id,
                "created_at": bd.created_at.isoformat(),
            }
            for bd in dumps
        ]
    }


@router.get("/dashboard")
async def get_dashboard(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Aggregated dashboard data."""
    from datetime import date

    today = date.today()
    today_start = datetime.combine(today, datetime.min.time())
    week_start = datetime.combine(today - timedelta(days=7), datetime.min.time())

    # Active objectives count
    obj_result = await session.execute(
        select(Objective).where(
            and_(Objective.user_id == user.id, Objective.status == "active")
        )
    )
    active_objectives = obj_result.scalars().all()

    # Open tasks count
    open_tasks = await get_open_tasks(session, user.id, limit=100)

    # Today's water
    water_result = await session.execute(
        select(Log).where(
            and_(Log.user_id == user.id, Log.log_type == "water", Log.logged_at >= today_start)
        )
    )
    water_today = sum(l.data.get("amount", 0) for l in water_result.scalars().all())

    # Workouts this week
    workout_result = await session.execute(
        select(Log).where(
            and_(Log.user_id == user.id, Log.log_type == "workout", Log.logged_at >= week_start)
        )
    )
    workouts_this_week = len(workout_result.scalars().all())

    # Latest mood
    mood_result = await session.execute(
        select(Log).where(
            and_(Log.user_id == user.id, Log.log_type == "mood")
        ).order_by(Log.logged_at.desc()).limit(1)
    )
    latest_mood = mood_result.scalar_one_or_none()

    # Routines + completions today
    routines = await get_active_routines(session, user.id)
    completed_today = await get_todays_completions(session, user.id)

    return {
        "user": {
            "id": user.id,
            "first_name": user.first_name,
            "timezone": user.timezone,
        },
        "stats": {
            "active_objectives": len(active_objectives),
            "open_tasks": len(open_tasks),
            "water_today_liters": round(water_today, 2),
            "workouts_this_week": workouts_this_week,
            "latest_mood": latest_mood.data.get("score") if latest_mood else None,
            "routines_total": len(routines),
            "routines_done_today": len([r for r in routines if r.id in completed_today]),
        },
    }


@router.post("/auth/token")
async def generate_token(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Regenerate API token for a user."""
    token = await generate_api_token(session, user)
    return {"token": token}
