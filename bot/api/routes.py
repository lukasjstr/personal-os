"""REST API routes — Phase 1–4 working endpoints + fitness + gamification."""
import math
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import and_, or_, select, delete as sql_delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from fastapi.responses import JSONResponse

from bot.api.auth import generate_api_token, get_current_user
from bot.core.brain_dumps import get_all_brain_dumps
from bot.core.routines import get_active_routines, get_todays_completions
from bot.core.tasks import get_open_tasks, get_open_shopping_items
from bot.database.connection import get_db
from bot.database.models import (
    BrainDump, CalendarEvent, FitnessSplit, KeyResult, Log, Objective, Routine,
    RoutineCompletion, Task, User,
)

router = APIRouter(prefix="/api")

LEVEL_TITLES = [
    "Rookie", "Beginner", "Learner", "Achiever", "Warrior",
    "Champion", "Master", "Expert", "Elite", "Legend", "Myth"
]


def get_level_title(level: int) -> str:
    idx = min(level, len(LEVEL_TITLES) - 1)
    return LEVEL_TITLES[idx]


@router.get("/health")
async def api_health() -> dict:
    return {"status": "ok", "version": "3.0.0"}


@router.get("/objectives")
async def list_objectives(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Get all objectives with key results."""
    result = await session.execute(
        select(Objective)
        .options(
            selectinload(Objective.key_results),
            selectinload(Objective.tasks),
        )
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
                "priority_weight": o.priority_weight,
                "parent_objective_id": o.parent_objective_id,
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
                "tasks": [
                    {
                        "id": t.id,
                        "title": t.title,
                        "status": t.status,
                        "priority": t.priority,
                        "parent_task_id": t.parent_task_id,
                    }
                    for t in sorted(o.tasks, key=lambda t: (t.status != "done", t.priority, t.id))
                ],
            }
            for o in objectives
        ]
    }


@router.get("/tasks")
async def list_tasks(
    status: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Get tasks with KR/objective info, optionally filtered by status and category."""
    conditions = [Task.user_id == user.id]
    if status:
        conditions.append(Task.status == status)
    else:
        conditions.append(Task.status.in_(["todo", "in_progress"]))
    if category:
        conditions.append(Task.category == category)

    result = await session.execute(
        select(Task)
        .options(
            selectinload(Task.key_result).selectinload(KeyResult.objective),
            selectinload(Task.objective),
        )
        .where(and_(*conditions))
        .order_by(Task.priority.asc(), Task.due_date.asc().nulls_last())
    )
    tasks = result.scalars().all()
    today = date.today()
    return {
        "tasks": [
            {
                "id": t.id,
                "title": t.title,
                "description": t.description,
                "status": t.status,
                "priority": t.priority,
                "category": t.category,
                "due_date": t.due_date.isoformat() if t.due_date else None,
                "is_overdue": bool(t.due_date and t.due_date < today and t.status not in ("done", "cancelled")),
                "completed_at": t.completed_at.isoformat() if t.completed_at else None,
                "key_result_id": t.key_result_id,
                "objective_id": t.objective_id,
                "parent_task_id": t.parent_task_id,
                "blocked_by_task_id": t.blocked_by_task_id,
                "key_result_title": t.key_result.title if t.key_result else None,
                "objective_title": (
                    t.objective.title if t.objective
                    else (t.key_result.objective.title if t.key_result and t.key_result.objective else None)
                ),
                "created_at": t.created_at.isoformat(),
            }
            for t in tasks
        ]
    }


@router.get("/shopping")
async def list_shopping(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Get open shopping items."""
    items = await get_open_shopping_items(session, user.id)
    return {
        "items": [
            {"id": t.id, "title": t.title, "created_at": t.created_at.isoformat()}
            for t in items
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


def _event_dict(e: CalendarEvent) -> dict:
    return {
        "id": e.id,
        "title": e.title,
        "description": e.description,
        "start_time": e.start_time.isoformat(),
        "end_time": e.end_time.isoformat() if e.end_time else None,
        "all_day": e.all_day,
        "event_type": e.event_type,
        "linked_task_id": e.linked_task_id,
    }


@router.get("/calendar")
async def list_calendar(
    days: int = Query(30, ge=1, le=365),
    days_past: int = Query(0, ge=0, le=365),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Get calendar events within a range (days_past ago → days ahead)."""
    now = datetime.utcnow()
    start = now - timedelta(days=days_past)
    end = now + timedelta(days=days)
    result = await session.execute(
        select(CalendarEvent)
        .where(and_(
            CalendarEvent.user_id == user.id,
            CalendarEvent.start_time >= start,
            CalendarEvent.start_time <= end,
        ))
        .order_by(CalendarEvent.start_time)
    )
    events = result.scalars().all()
    return {"events": [_event_dict(e) for e in events]}


class CalendarEventUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    all_day: Optional[bool] = None
    event_type: Optional[str] = None


class CalendarNoteUpdate(BaseModel):
    notes: str


@router.put("/calendar/{event_id}")
async def update_calendar_event(
    event_id: int,
    body: CalendarEventUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Update a calendar event."""
    result = await session.execute(
        select(CalendarEvent).where(
            CalendarEvent.id == event_id,
            CalendarEvent.user_id == user.id,
        )
    )
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Event nicht gefunden")

    if body.title is not None:
        event.title = body.title
    if body.description is not None:
        event.description = body.description
    if body.all_day is not None:
        event.all_day = body.all_day
    if body.event_type is not None:
        event.event_type = body.event_type
    if body.start_time is not None:
        from bot.core.calendar import create_calendar_event as _ccal  # noqa: F401
        fmts = ["%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M", "%Y-%m-%d"]
        for fmt in fmts:
            try:
                event.start_time = datetime.strptime(body.start_time, fmt)
                break
            except ValueError:
                continue
    if body.end_time is not None:
        fmts = ["%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M", "%Y-%m-%d"]
        for fmt in fmts:
            try:
                event.end_time = datetime.strptime(body.end_time, fmt)
                break
            except ValueError:
                continue

    await session.flush()
    return _event_dict(event)


@router.post("/calendar/{event_id}/notes")
async def add_calendar_notes(
    event_id: int,
    body: CalendarNoteUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Add or update notes for a calendar event."""
    result = await session.execute(
        select(CalendarEvent).where(
            CalendarEvent.id == event_id,
            CalendarEvent.user_id == user.id,
        )
    )
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Event nicht gefunden")

    event.description = body.notes
    await session.flush()
    return _event_dict(event)


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
    """Aggregated dashboard data with XP, level, and streak."""
    from datetime import date
    today = date.today()
    today_start = datetime.combine(today, datetime.min.time())
    week_start = datetime.combine(today - timedelta(days=7), datetime.min.time())
    since_60 = datetime.combine(today - timedelta(days=60), datetime.min.time())

    obj_result = await session.execute(
        select(Objective).where(and_(Objective.user_id == user.id, Objective.status == "active"))
    )
    active_objectives = obj_result.scalars().all()

    open_tasks = await get_open_tasks(session, user.id, limit=100)
    shopping_items = await get_open_shopping_items(session, user.id)

    water_result = await session.execute(
        select(Log).where(
            and_(Log.user_id == user.id, Log.log_type == "water", Log.logged_at >= today_start)
        )
    )
    water_today = sum(l.data.get("amount", 0) for l in water_result.scalars().all())

    workout_result = await session.execute(
        select(Log).where(
            and_(Log.user_id == user.id, Log.log_type == "workout", Log.logged_at >= week_start)
        )
    )
    workouts_this_week = len(workout_result.scalars().all())

    mood_result = await session.execute(
        select(Log).where(
            and_(Log.user_id == user.id, Log.log_type == "mood")
        ).order_by(Log.logged_at.desc()).limit(1)
    )
    latest_mood = mood_result.scalar_one_or_none()

    routines = await get_active_routines(session, user.id)
    completed_today = await get_todays_completions(session, user.id)

    # ── Streak calculation ──────────────────────────────────────────────────
    log_dates_result = await session.execute(
        select(Log.logged_at).where(
            and_(Log.user_id == user.id, Log.logged_at >= since_60)
        )
    )
    all_log_dates = {dt.date() for dt in log_dates_result.scalars().all()}
    streak = 0
    check_date = today
    while check_date in all_log_dates:
        streak += 1
        check_date -= timedelta(days=1)

    # ── XP / Level calculation ──────────────────────────────────────────────
    done_tasks_result = await session.execute(
        select(Task).where(and_(Task.user_id == user.id, Task.status == "done"))
    )
    done_tasks_count = len(done_tasks_result.scalars().all())

    workout_dates_result = await session.execute(
        select(Log.logged_at).where(and_(Log.user_id == user.id, Log.log_type == "workout"))
    )
    workout_sessions = len({dt.date() for dt in workout_dates_result.scalars().all()})

    rc_result = await session.execute(
        select(RoutineCompletion).where(RoutineCompletion.user_id == user.id)
    )
    rc_count = len(rc_result.scalars().all())

    mood_count_result = await session.execute(
        select(Log).where(and_(Log.user_id == user.id, Log.log_type == "mood"))
    )
    mood_count = len(mood_count_result.scalars().all())

    total_xp = done_tasks_count * 10 + workout_sessions * 25 + rc_count * 15 + mood_count * 5
    level = math.floor(math.sqrt(total_xp / 100)) if total_xp > 0 else 0
    xp_for_current = level * level * 100
    xp_for_next = (level + 1) * (level + 1) * 100

    return {
        "user": {
            "id": user.id,
            "first_name": user.first_name,
            "timezone": user.timezone,
        },
        "stats": {
            "active_objectives": len(active_objectives),
            "open_tasks": len(open_tasks),
            "shopping_items": len(shopping_items),
            "water_today_liters": round(water_today, 2),
            "workouts_this_week": workouts_this_week,
            "latest_mood": latest_mood.data.get("score") if latest_mood else None,
            "routines_total": len(routines),
            "routines_done_today": len([r for r in routines if r.id in completed_today]),
            "streak_days": streak,
            "total_xp": total_xp,
            "level": level,
            "level_title": get_level_title(level),
            "xp_progress": total_xp - xp_for_current,
            "xp_to_next": xp_for_next - xp_for_current,
        },
    }


# ─── Fitness Endpoints ─────────────────────────────────────────────────────────

@router.get("/fitness/summary")
async def get_fitness_summary(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Get fitness summary: last sessions, volume trend, workout days."""
    since_90 = datetime.utcnow() - timedelta(days=90)
    result = await session.execute(
        select(Log).where(
            and_(Log.user_id == user.id, Log.log_type == "workout", Log.logged_at >= since_90)
        ).order_by(Log.logged_at.desc())
    )
    workout_logs = result.scalars().all()

    workout_days = set()
    for l in workout_logs:
        workout_days.add(l.logged_at.date())

    volume_by_week: dict = defaultdict(float)
    for l in workout_logs:
        week_key = l.logged_at.strftime("%Y-W%W")
        weight = float(l.data.get("weight", 0) or 0)
        reps = float(l.data.get("reps", 1) or 1)
        sets = float(l.data.get("sets", 1) or 1)
        if weight > 0:
            volume_by_week[week_key] += weight * reps * sets

    sessions_by_day: dict = {}
    for l in workout_logs:
        day = l.logged_at.date().isoformat()
        if day not in sessions_by_day:
            sessions_by_day[day] = []
        sessions_by_day[day].append({
            "exercise": l.data.get("exercise", "?"),
            "weight": l.data.get("weight"),
            "reps": l.data.get("reps"),
            "sets": l.data.get("sets"),
            "duration_min": l.data.get("duration_min"),
        })

    last_sessions = [
        {"date": day, "exercises": exs}
        for day, exs in sorted(sessions_by_day.items(), reverse=True)[:8]
    ]

    return {
        "total_workout_days": len(workout_days),
        "workout_days": sorted([d.isoformat() for d in workout_days]),
        "volume_by_week": [
            {"week": week, "volume": round(vol)}
            for week, vol in sorted(volume_by_week.items())[-12:]
        ],
        "last_sessions": last_sessions,
    }


@router.get("/fitness/exercises")
async def get_fitness_exercises(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Get stats per exercise."""
    result = await session.execute(
        select(Log).where(
            and_(Log.user_id == user.id, Log.log_type == "workout")
        ).order_by(Log.logged_at.desc())
    )
    workout_logs = result.scalars().all()

    exercises: dict = {}
    for l in workout_logs:
        ex = str(l.data.get("exercise", "Unbekannt")).strip()
        if ex not in exercises:
            exercises[ex] = {
                "name": ex,
                "count": 0,
                "max_weight": 0.0,
                "last_done": l.logged_at.isoformat(),
            }
        exercises[ex]["count"] += 1
        weight = float(l.data.get("weight", 0) or 0)
        if weight > exercises[ex]["max_weight"]:
            exercises[ex]["max_weight"] = weight

    return {
        "exercises": sorted(exercises.values(), key=lambda x: -x["count"])
    }


@router.get("/fitness/prs")
async def get_fitness_prs(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Get personal records (max weight per exercise)."""
    result = await session.execute(
        select(Log).where(
            and_(Log.user_id == user.id, Log.log_type == "workout")
        )
    )
    workout_logs = result.scalars().all()

    prs: dict = {}
    for l in workout_logs:
        ex = str(l.data.get("exercise", "Unbekannt")).strip()
        weight = float(l.data.get("weight", 0) or 0)
        reps = l.data.get("reps")
        if weight > 0:
            if ex not in prs or weight > prs[ex]["weight"]:
                prs[ex] = {
                    "exercise": ex,
                    "weight": weight,
                    "reps": reps,
                    "date": l.logged_at.isoformat(),
                }

    return {
        "prs": sorted(prs.values(), key=lambda x: -x["weight"])
    }


# ─── Fitness Split Endpoints ───────────────────────────────────────────────────

class _SplitExercise(BaseModel):
    name: str
    sets: Optional[int] = None
    reps: Optional[str] = None
    target_weight: Optional[float] = None


class _CreateFitnessSplitBody(BaseModel):
    name: str
    exercises: list[_SplitExercise]
    day_of_week: Optional[int] = None
    order_in_rotation: Optional[int] = None


@router.get("/fitness/splits")
async def get_fitness_splits(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Get all fitness splits with usage stats and next-split recommendation."""
    result = await session.execute(
        select(FitnessSplit)
        .where(FitnessSplit.user_id == user.id)
        .order_by(FitnessSplit.order_in_rotation.nulls_last(), FitnessSplit.created_at)
    )
    splits = result.scalars().all()

    # Recent logs to determine usage + last split used
    since_30 = datetime.utcnow() - timedelta(days=30)
    log_result = await session.execute(
        select(Log)
        .where(and_(Log.user_id == user.id, Log.log_type == "workout", Log.logged_at >= since_30))
        .order_by(Log.logged_at.desc())
    )
    recent_logs = log_result.scalars().all()

    split_usage: dict = defaultdict(int)
    last_used: dict = {}
    last_split_id = None
    for log in recent_logs:
        sid = log.data.get("split_id")
        if sid:
            split_usage[sid] += 1
            if sid not in last_used:
                last_used[sid] = log.logged_at.date().isoformat()
            if last_split_id is None:
                last_split_id = sid

    split_ids = [s.id for s in splits]
    next_split_id = None
    if split_ids:
        if last_split_id and last_split_id in split_ids:
            idx = split_ids.index(last_split_id)
            next_split_id = split_ids[(idx + 1) % len(split_ids)]
        else:
            next_split_id = split_ids[0]

    return {
        "splits": [
            {
                "id": s.id,
                "name": s.name,
                "exercises": s.exercises,
                "day_of_week": s.day_of_week,
                "order_in_rotation": s.order_in_rotation,
                "created_at": s.created_at.isoformat(),
                "workout_count": split_usage.get(s.id, 0),
                "last_used": last_used.get(s.id),
                "is_next": s.id == next_split_id,
            }
            for s in splits
        ],
        "next_split_id": next_split_id,
    }


@router.post("/fitness/splits")
async def create_fitness_split_api(
    body: _CreateFitnessSplitBody,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Create a new fitness split."""
    split = FitnessSplit(
        user_id=user.id,
        name=body.name,
        exercises=[ex.model_dump(exclude_none=True) for ex in body.exercises],
        day_of_week=body.day_of_week,
        order_in_rotation=body.order_in_rotation,
    )
    session.add(split)
    await session.flush()
    await session.commit()
    return {
        "id": split.id,
        "name": split.name,
        "exercises": split.exercises,
        "day_of_week": split.day_of_week,
        "order_in_rotation": split.order_in_rotation,
        "created_at": split.created_at.isoformat(),
    }


@router.get("/fitness/progression/{exercise}")
async def get_exercise_progression(
    exercise: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Get weight progression for a specific exercise over time."""
    result = await session.execute(
        select(Log)
        .where(and_(Log.user_id == user.id, Log.log_type == "workout"))
        .order_by(Log.logged_at.asc())
    )
    workout_logs = result.scalars().all()

    exercise_lower = exercise.lower()
    data_points = []
    seen_dates: set = set()
    for log in workout_logs:
        if str(log.data.get("exercise", "")).lower() == exercise_lower:
            weight = float(log.data.get("weight", 0) or 0)
            if weight > 0:
                day = log.logged_at.date().isoformat()
                if day in seen_dates:
                    # Keep highest weight per day
                    for dp in data_points:
                        if dp["date"] == day and weight > dp["weight"]:
                            dp["weight"] = weight
                            dp["reps"] = log.data.get("reps")
                            dp["sets"] = log.data.get("sets")
                else:
                    seen_dates.add(day)
                    data_points.append({
                        "date": day,
                        "weight": weight,
                        "reps": log.data.get("reps"),
                        "sets": log.data.get("sets"),
                    })

    return {
        "exercise": exercise,
        "data_points": data_points,
    }


# ─── Phase 4 Endpoints ────────────────────────────────────────────────────────

@router.get("/weekly-summary")
async def get_weekly_summary(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Weekly summary: tasks done, objectives progress, workout count, mood trend."""
    today = date.today()
    week_start = today - timedelta(days=today.weekday())  # Monday
    week_start_dt = datetime.combine(week_start, datetime.min.time())
    week_end_dt = datetime.combine(today, datetime.max.time())

    # Tasks completed this week
    done_result = await session.execute(
        select(Task).where(and_(
            Task.user_id == user.id,
            Task.status == "done",
            Task.completed_at >= week_start_dt,
            Task.completed_at <= week_end_dt,
            Task.category != "shopping",
        ))
    )
    done_tasks = done_result.scalars().all()

    # Still open tasks
    open_result = await session.execute(
        select(Task).where(and_(
            Task.user_id == user.id,
            Task.status.in_(["todo", "in_progress"]),
            Task.category != "shopping",
        ))
    )
    open_tasks = open_result.scalars().all()

    # Workout days this week
    workout_result = await session.execute(
        select(Log).where(and_(
            Log.user_id == user.id,
            Log.log_type == "workout",
            Log.logged_at >= week_start_dt,
            Log.logged_at <= week_end_dt,
        ))
    )
    workout_days = len({l.logged_at.date() for l in workout_result.scalars().all()})

    # Mood trend this week
    mood_result = await session.execute(
        select(Log).where(and_(
            Log.user_id == user.id,
            Log.log_type == "mood",
            Log.logged_at >= week_start_dt,
            Log.logged_at <= week_end_dt,
        )).order_by(Log.logged_at.asc())
    )
    mood_logs = mood_result.scalars().all()
    mood_scores = [l.data.get("score") for l in mood_logs if l.data.get("score")]
    mood_avg = round(sum(mood_scores) / len(mood_scores), 1) if mood_scores else None

    # Routine completion rate this week
    routine_result = await session.execute(
        select(Routine).where(and_(Routine.user_id == user.id, Routine.status == "active"))
    )
    routines = routine_result.scalars().all()

    comp_result = await session.execute(
        select(RoutineCompletion).where(and_(
            RoutineCompletion.user_id == user.id,
            RoutineCompletion.completed_at >= week_start_dt,
            RoutineCompletion.completed_at <= week_end_dt,
        ))
    )
    completions = comp_result.scalars().all()
    days_elapsed = (today - week_start).days + 1
    max_completions = len(routines) * days_elapsed
    routine_rate = round(len(completions) / max_completions * 100) if max_completions > 0 else 0

    # Water average this week
    water_result = await session.execute(
        select(Log).where(and_(
            Log.user_id == user.id,
            Log.log_type == "water",
            Log.logged_at >= week_start_dt,
            Log.logged_at <= week_end_dt,
        ))
    )
    water_by_day: dict = defaultdict(float)
    for l in water_result.scalars().all():
        water_by_day[l.logged_at.date().isoformat()] += l.data.get("amount", 0)
    water_avg = round(sum(water_by_day.values()) / len(water_by_day), 2) if water_by_day else 0

    return {
        "week_start": week_start.isoformat(),
        "tasks_done_this_week": len(done_tasks),
        "tasks_open": len(open_tasks),
        "workout_days": workout_days,
        "routine_completion_rate": routine_rate,
        "mood_avg": mood_avg,
        "mood_scores": mood_scores,
        "water_avg_liters": water_avg,
    }


@router.get("/priorities")
async def get_priorities(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Top 5 priorities scored from: priority level, due date, objective importance."""
    today = date.today()

    result = await session.execute(
        select(Task)
        .options(selectinload(Task.key_result).selectinload(KeyResult.objective))
        .where(and_(
            Task.user_id == user.id,
            Task.status.in_(["todo", "in_progress"]),
            Task.category != "shopping",
        ))
    )
    tasks = result.scalars().all()

    scored = []
    for t in tasks:
        # Base score from priority (P1=50, P2=40, P3=30, P4=20, P5=10)
        score = (6 - t.priority) * 10

        # Due date bonuses
        if t.due_date:
            if t.due_date < today:
                score += 40  # overdue
            elif t.due_date == today:
                score += 30  # due today
            elif t.due_date <= today + timedelta(days=2):
                score += 20  # due in 2 days
            elif t.due_date <= today + timedelta(days=7):
                score += 10  # due this week

        # Objective importance bonus
        if t.key_result and t.key_result.objective:
            score += t.key_result.objective.priority_weight * 1

        scored.append((score, t))

    scored.sort(key=lambda x: -x[0])
    top5 = scored[:5]

    return {
        "priorities": [
            {
                "rank": i + 1,
                "score": s,
                "task_id": t.id,
                "title": t.title,
                "priority": t.priority,
                "category": t.category,
                "due_date": t.due_date.isoformat() if t.due_date else None,
                "is_overdue": bool(t.due_date and t.due_date < today),
                "objective_title": t.key_result.objective.title if t.key_result and t.key_result.objective else None,
            }
            for i, (s, t) in enumerate(top5)
        ]
    }


@router.get("/routines/history")
async def get_routines_history(
    days: int = Query(7, ge=1, le=30),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Get routine completions for the last N days (default 7) for streak grid."""
    today = date.today()
    start_date = today - timedelta(days=days - 1)
    start_dt = datetime.combine(start_date, datetime.min.time())

    routines = await get_active_routines(session, user.id)

    comp_result = await session.execute(
        select(RoutineCompletion).where(and_(
            RoutineCompletion.user_id == user.id,
            RoutineCompletion.completed_at >= start_dt,
        ))
    )
    completions = comp_result.scalars().all()

    by_routine: dict[int, set[str]] = {}
    for c in completions:
        rid = c.routine_id
        if rid not in by_routine:
            by_routine[rid] = set()
        by_routine[rid].add(c.completed_at.date().isoformat())

    all_days = [(start_date + timedelta(days=i)).isoformat() for i in range(days)]

    def calc_streak(dates: set[str]) -> int:
        streak = 0
        d = today
        while d.isoformat() in dates:
            streak += 1
            d -= timedelta(days=1)
        if streak == 0 and (today - timedelta(days=1)).isoformat() in dates:
            # Started streak counting from yesterday
            d = today - timedelta(days=1)
            while d.isoformat() in dates:
                streak += 1
                d -= timedelta(days=1)
        return streak

    return {
        "days": all_days,
        "routines": [
            {
                "id": r.id,
                "title": r.title,
                "completions": sorted(by_routine.get(r.id, set())),
                "streak": calc_streak(by_routine.get(r.id, set())),
            }
            for r in routines
        ],
    }


@router.post("/tasks/{task_id}/complete")
async def complete_task_endpoint(
    task_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Mark a task as done from the dashboard."""
    result = await session.execute(
        select(Task).where(and_(Task.id == task_id, Task.user_id == user.id))
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status == "done":
        return {"ok": True, "message": "Already done"}

    task.status = "done"
    task.completed_at = datetime.utcnow()
    await session.flush()
    return {"ok": True, "task_id": task_id, "title": task.title}


@router.post("/routines/{routine_id}/complete")
async def complete_routine_endpoint(
    routine_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Mark a routine as done for today from the dashboard."""
    result = await session.execute(
        select(Routine).where(and_(Routine.id == routine_id, Routine.user_id == user.id))
    )
    routine = result.scalar_one_or_none()
    if not routine:
        raise HTTPException(status_code=404, detail="Routine not found")

    today_start = datetime.combine(date.today(), datetime.min.time())
    already = await session.execute(
        select(RoutineCompletion).where(and_(
            RoutineCompletion.routine_id == routine_id,
            RoutineCompletion.user_id == user.id,
            RoutineCompletion.completed_at >= today_start,
        ))
    )
    if already.scalar_one_or_none():
        return {"ok": True, "message": "Already completed today"}

    completion = RoutineCompletion(
        routine_id=routine_id,
        user_id=user.id,
        completed_at=datetime.utcnow(),
    )
    session.add(completion)
    await session.flush()
    return {"ok": True, "routine_id": routine_id, "title": routine.title}


@router.get("/brief/today")
async def get_todays_brief(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Get today's daily brief priorities snapshot."""
    from bot.database.models import DailyBrief
    today = date.today()
    result = await session.execute(
        select(DailyBrief).where(and_(
            DailyBrief.user_id == user.id,
            DailyBrief.brief_date == today,
        ))
    )
    brief = result.scalar_one_or_none()
    return {
        "brief_sent": brief.brief_sent_at.isoformat() if brief and brief.brief_sent_at else None,
        "review_sent": brief.review_sent_at.isoformat() if brief and brief.review_sent_at else None,
        "day_score": brief.day_score if brief else None,
    }


@router.post("/auth/token")
async def generate_token(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Regenerate API token for a user."""
    token = await generate_api_token(session, user)
    return {"token": token}


# ─── CRUD: Pydantic request bodies ────────────────────────────────────────────

class UpdateObjectiveBody(BaseModel):
    title: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    target_date: Optional[str] = None
    status: Optional[str] = None


class UpdateTaskBody(BaseModel):
    title: Optional[str] = None
    category: Optional[str] = None
    priority: Optional[int] = None
    due_date: Optional[str] = None
    status: Optional[str] = None
    objective_id: Optional[int] = None


class UpdateRoutineBody(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    frequency_human: Optional[str] = None
    status: Optional[str] = None


class UpdateBrainDumpBody(BaseModel):
    raw_input: Optional[str] = None


# ─── Objectives CRUD ──────────────────────────────────────────────────────────

@router.put("/objectives/{objective_id}")
async def update_objective(
    objective_id: int,
    body: UpdateObjectiveBody,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Update an objective."""
    result = await session.execute(
        select(Objective).where(and_(Objective.id == objective_id, Objective.user_id == user.id))
    )
    obj = result.scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="Objective not found")

    if body.title is not None:
        obj.title = body.title
    if body.category is not None:
        obj.category = body.category
    if body.description is not None:
        obj.description = body.description if body.description else None
    if body.target_date is not None:
        try:
            obj.target_date = date.fromisoformat(body.target_date) if body.target_date else None
        except ValueError:
            pass
    if body.status is not None:
        obj.status = body.status

    await session.flush()
    return {"ok": True, "id": objective_id}


@router.delete("/objectives/{objective_id}")
async def delete_objective(
    objective_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Delete objective + cascade to its KRs and Tasks."""
    result = await session.execute(
        select(Objective)
        .options(selectinload(Objective.key_results))
        .where(and_(Objective.id == objective_id, Objective.user_id == user.id))
    )
    obj = result.scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="Objective not found")

    kr_ids = [kr.id for kr in obj.key_results]

    # Delete tasks linked to this objective or its key results
    if kr_ids:
        task_filter = or_(Task.objective_id == objective_id, Task.key_result_id.in_(kr_ids))
    else:
        task_filter = Task.objective_id == objective_id

    await session.execute(
        sql_delete(Task).where(and_(Task.user_id == user.id, task_filter))
    )

    # Delete objective (cascades to key_results via ORM cascade)
    await session.delete(obj)
    await session.flush()
    return {"ok": True, "deleted_id": objective_id}


# ─── Tasks CRUD ───────────────────────────────────────────────────────────────

@router.put("/tasks/{task_id}")
async def update_task(
    task_id: int,
    body: UpdateTaskBody,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Update a task."""
    result = await session.execute(
        select(Task).where(and_(Task.id == task_id, Task.user_id == user.id))
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if body.title is not None:
        task.title = body.title
    if body.category is not None:
        task.category = body.category if body.category else None
    if body.priority is not None:
        task.priority = max(1, min(5, body.priority))
    if body.due_date is not None:
        try:
            task.due_date = date.fromisoformat(body.due_date) if body.due_date else None
        except ValueError:
            pass
    if body.status is not None:
        task.status = body.status
        if body.status == "done" and not task.completed_at:
            task.completed_at = datetime.utcnow()
    if body.objective_id is not None:
        task.objective_id = body.objective_id if body.objective_id > 0 else None

    await session.flush()
    return {"ok": True, "id": task_id}


@router.delete("/tasks/{task_id}")
async def delete_task(
    task_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Delete a task."""
    result = await session.execute(
        select(Task).where(and_(Task.id == task_id, Task.user_id == user.id))
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    await session.delete(task)
    await session.flush()
    return {"ok": True, "deleted_id": task_id}


# ─── Routines CRUD ────────────────────────────────────────────────────────────

@router.put("/routines/{routine_id}")
async def update_routine(
    routine_id: int,
    body: UpdateRoutineBody,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Update a routine."""
    result = await session.execute(
        select(Routine).where(and_(Routine.id == routine_id, Routine.user_id == user.id))
    )
    routine = result.scalar_one_or_none()
    if not routine:
        raise HTTPException(status_code=404, detail="Routine not found")

    if body.title is not None:
        routine.title = body.title
    if body.description is not None:
        routine.description = body.description if body.description else None
    if body.frequency_human is not None:
        routine.frequency_human = body.frequency_human if body.frequency_human else None
    if body.status is not None:
        routine.status = body.status

    await session.flush()
    return {"ok": True, "id": routine_id}


@router.delete("/routines/{routine_id}")
async def delete_routine(
    routine_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Delete a routine and its completion history."""
    result = await session.execute(
        select(Routine).where(and_(Routine.id == routine_id, Routine.user_id == user.id))
    )
    routine = result.scalar_one_or_none()
    if not routine:
        raise HTTPException(status_code=404, detail="Routine not found")

    await session.delete(routine)
    await session.flush()
    return {"ok": True, "deleted_id": routine_id}


# ─── Brain Dumps CRUD ─────────────────────────────────────────────────────────

@router.put("/brain-dumps/{dump_id}")
async def update_brain_dump(
    dump_id: int,
    body: UpdateBrainDumpBody,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Update a brain dump."""
    result = await session.execute(
        select(BrainDump).where(and_(BrainDump.id == dump_id, BrainDump.user_id == user.id))
    )
    dump = result.scalar_one_or_none()
    if not dump:
        raise HTTPException(status_code=404, detail="Brain dump not found")

    if body.raw_input is not None:
        dump.raw_input = body.raw_input

    await session.flush()
    return {"ok": True, "id": dump_id}


@router.delete("/brain-dumps/{dump_id}")
async def delete_brain_dump(
    dump_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Delete a brain dump."""
    result = await session.execute(
        select(BrainDump).where(and_(BrainDump.id == dump_id, BrainDump.user_id == user.id))
    )
    dump = result.scalar_one_or_none()
    if not dump:
        raise HTTPException(status_code=404, detail="Brain dump not found")

    await session.delete(dump)
    await session.flush()
    return {"ok": True, "deleted_id": dump_id}


# ─── Logs CRUD ────────────────────────────────────────────────────────────────

@router.delete("/logs/{log_id}")
async def delete_log(
    log_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Delete a log entry."""
    result = await session.execute(
        select(Log).where(and_(Log.id == log_id, Log.user_id == user.id))
    )
    log = result.scalar_one_or_none()
    if not log:
        raise HTTPException(status_code=404, detail="Log not found")

    await session.delete(log)
    await session.flush()
    return {"ok": True, "deleted_id": log_id}


# ─── Settings Endpoints ────────────────────────────────────────────────────────

class UpdateProfileBody(BaseModel):
    first_name: Optional[str] = None


class UpdateSettingsBody(BaseModel):
    priorities_enabled: Optional[bool] = None
    review_enabled: Optional[bool] = None
    proactive_enabled: Optional[bool] = None
    reflection_enabled: Optional[bool] = None
    morning_brief_time: Optional[str] = None
    evening_review_time: Optional[str] = None
    weekly_reflection_day: Optional[str] = None
    weekly_reflection_time: Optional[str] = None
    category_weights: Optional[dict] = None


@router.get("/settings")
async def get_settings(
    user: User = Depends(get_current_user),
) -> dict:
    """Get user profile and settings."""
    s = user.settings or {}
    return {
        "profile": {
            "first_name": user.first_name,
            "telegram_username": user.telegram_username,
            "timezone": user.timezone,
        },
        "toggles": {
            "priorities_enabled": s.get("priorities_enabled", True),
            "review_enabled": s.get("review_enabled", True),
            "proactive_enabled": s.get("proactive_enabled", True),
            "reflection_enabled": s.get("reflection_enabled", False),
        },
        "times": {
            "morning_brief_time": s.get("morning_brief_time", "06:30"),
            "evening_review_time": s.get("evening_review_time", "21:00"),
            "weekly_reflection_day": s.get("weekly_reflection_day", "sunday"),
            "weekly_reflection_time": s.get("weekly_reflection_time", "19:00"),
        },
        "category_weights": s.get("category_weights", {}),
    }


@router.put("/settings/profile")
async def update_profile(
    body: UpdateProfileBody,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Update user profile (name)."""
    if body.first_name is not None:
        stripped = body.first_name.strip()
        if stripped:
            user.first_name = stripped
    await session.flush()
    return {"ok": True, "first_name": user.first_name}


@router.put("/settings")
async def update_settings(
    body: UpdateSettingsBody,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Update user settings (toggles, times, category weights)."""
    settings = dict(user.settings or {})
    if body.priorities_enabled is not None:
        settings["priorities_enabled"] = body.priorities_enabled
    if body.review_enabled is not None:
        settings["review_enabled"] = body.review_enabled
    if body.proactive_enabled is not None:
        settings["proactive_enabled"] = body.proactive_enabled
    if body.reflection_enabled is not None:
        settings["reflection_enabled"] = body.reflection_enabled
    if body.morning_brief_time is not None:
        settings["morning_brief_time"] = body.morning_brief_time
    if body.evening_review_time is not None:
        settings["evening_review_time"] = body.evening_review_time
    if body.weekly_reflection_day is not None:
        settings["weekly_reflection_day"] = body.weekly_reflection_day
    if body.weekly_reflection_time is not None:
        settings["weekly_reflection_time"] = body.weekly_reflection_time
    if body.category_weights is not None:
        settings["category_weights"] = body.category_weights
    user.settings = settings
    await session.flush()
    return {"ok": True}


@router.get("/settings/export")
async def export_data(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """Export all user data as JSON download."""
    obj_result = await session.execute(
        select(Objective)
        .options(selectinload(Objective.key_results))
        .where(Objective.user_id == user.id)
        .order_by(Objective.created_at)
    )
    objectives = obj_result.scalars().all()

    task_result = await session.execute(
        select(Task).where(Task.user_id == user.id).order_by(Task.created_at)
    )
    tasks = task_result.scalars().all()

    log_result = await session.execute(
        select(Log)
        .where(and_(Log.user_id == user.id, Log.logged_at >= datetime.utcnow() - timedelta(days=365)))
        .order_by(Log.logged_at)
    )
    logs = log_result.scalars().all()

    routine_result = await session.execute(
        select(Routine).where(Routine.user_id == user.id).order_by(Routine.created_at)
    )
    routines = routine_result.scalars().all()

    bd_result = await session.execute(
        select(BrainDump).where(BrainDump.user_id == user.id).order_by(BrainDump.created_at)
    )
    brain_dumps = bd_result.scalars().all()

    cal_result = await session.execute(
        select(CalendarEvent).where(CalendarEvent.user_id == user.id).order_by(CalendarEvent.start_time)
    )
    calendar_events = cal_result.scalars().all()

    payload = {
        "exported_at": datetime.utcnow().isoformat(),
        "profile": {
            "first_name": user.first_name,
            "telegram_username": user.telegram_username,
            "timezone": user.timezone,
            "settings": user.settings,
            "created_at": user.created_at.isoformat(),
        },
        "objectives": [
            {
                "id": o.id,
                "title": o.title,
                "description": o.description,
                "category": o.category,
                "status": o.status,
                "priority_weight": o.priority_weight,
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
                    }
                    for kr in o.key_results
                ],
            }
            for o in objectives
        ],
        "tasks": [
            {
                "id": t.id,
                "title": t.title,
                "description": t.description,
                "status": t.status,
                "priority": t.priority,
                "category": t.category,
                "due_date": t.due_date.isoformat() if t.due_date else None,
                "completed_at": t.completed_at.isoformat() if t.completed_at else None,
                "created_at": t.created_at.isoformat(),
            }
            for t in tasks
        ],
        "routines": [
            {
                "id": r.id,
                "title": r.title,
                "description": r.description,
                "frequency_human": r.frequency_human,
                "status": r.status,
                "created_at": r.created_at.isoformat(),
            }
            for r in routines
        ],
        "logs": [
            {
                "id": l.id,
                "log_type": l.log_type,
                "data": l.data,
                "source": l.source,
                "raw_input": l.raw_input,
                "logged_at": l.logged_at.isoformat(),
            }
            for l in logs
        ],
        "brain_dumps": [
            {
                "id": bd.id,
                "raw_input": bd.raw_input,
                "processed": bd.processed,
                "ai_interpretation": bd.ai_interpretation,
                "created_at": bd.created_at.isoformat(),
            }
            for bd in brain_dumps
        ],
        "calendar_events": [
            {
                "id": e.id,
                "title": e.title,
                "start_time": e.start_time.isoformat(),
                "end_time": e.end_time.isoformat() if e.end_time else None,
                "all_day": e.all_day,
                "event_type": e.event_type,
            }
            for e in calendar_events
        ],
    }

    return JSONResponse(
        content=payload,
        headers={"Content-Disposition": f"attachment; filename=personal-os-export.json"},
    )


@router.delete("/settings/account")
async def delete_account(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Delete user account and all associated data."""
    await session.delete(user)
    await session.flush()
    return {"ok": True}
