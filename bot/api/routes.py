"""REST API routes — Phase 1–4 working endpoints + fitness + gamification."""
import dataclasses
import math
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel, field_validator
from sqlalchemy import and_, extract, func, or_, select, delete as sql_delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from fastapi.responses import JSONResponse

from bot.api.auth import generate_api_token, get_current_user
from bot.core.brain_dumps import get_all_brain_dumps
from bot.core.explainability import get_task_reason as _get_task_reason
from bot.core.gamification import add_xp as _add_xp, get_level, get_level_title
from bot.core.routines import get_active_routines, get_todays_completions
from bot.core.tasks import get_open_tasks, get_open_shopping_items
from bot.database.connection import get_db
from bot.database.models import (
    Achievement, ActionQueueItem, AutomationRule, AutopilotNotification, BrainDump, CalendarEvent,
    Commitment, Contact, DailyBrief,
    DailyContext, DailySuggestion, EveningCheckin, FitnessSplit, Interaction, KeyResult,
    LearningItem, LearningReview, LifeProfile, Log, NodeRelation,
    Objective, ObjectiveTaskSuggestion,
    OKRProposalDraft, QuarterlyReview, Routine, RoutineCompletion, RoutineObjectiveImpact, ScheduledReminder,
    ShoppingDefault, Task, User, UserAchievement, WeeklyReflection, WorkoutLog,
    VALID_NODE_TYPES, VALID_RELATION_TYPES,
)
from bot.jobs.daily_suggestions import get_or_generate_suggestions
from bot.core.okr_generator import OKRDraft, generate_okr_draft_fallback
from bot.core.reminder_factory import ReminderConfig, generate_reminder_drafts
from bot.core.reminder_engine import dry_run_preview
from bot.core.slot_candidates import derive_slot_candidates
from bot.core.slot_conflict_detection import detect_conflicts
from bot.telegram.sender import send_message

router = APIRouter(prefix="/api")


@router.get("/health")
async def api_health(session: AsyncSession = Depends(get_db)) -> dict:
    from bot.core.monitoring import health_probe
    probe = await health_probe(session)
    return {"status": "ok", "version": "8.0.0", **probe}


@router.get("/health/daily")
async def get_daily_health(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Return today's supplement stack, fitness split, macros, and last weights."""
    today = date.today()

    # Supplement stacks (with cycle gating)
    supplements: dict = {"morning": [], "midday": [], "evening": []}
    macros: dict = {}
    try:
        from bot.core.supplement_protocol import generate_daily_checklist, load_protocol
        protocol = load_protocol()
        checklist = generate_daily_checklist(protocol, today)
        for slot in ("morning", "midday", "evening"):
            supplements[slot] = [
                {"name": s.get("name", ""), "dose": s.get("dose", "")}
                for s in checklist["slot_checklist"][slot]
                if s.get("name")
            ]
        mt = protocol.get("macro_targets", {})
        hyd = protocol.get("hydration", {})
        water_str = f"{hyd.get('water_l_min', 2.5)}-{hyd.get('water_l_max', 3.5)}L"
        macros = {
            "calories": mt.get("calories_kcal", 0),
            "protein": mt.get("protein_g", 0),
            "carbs": mt.get("net_carbs_max_g", 0),
            "fat": mt.get("fat_g", 0),
            "water": water_str,
        }
    except Exception:
        pass

    # Fitness split (config-driven rotation)
    fitness: dict = {"split": None, "focus": None, "exercises": [], "is_rest_day": False}
    try:
        from bot.core.fitness_protocol import get_today_split, load_fitness_protocol
        fp = load_fitness_protocol()
        split = get_today_split(fp, today)
        fitness = {
            "split": split.get("split_name"),
            "focus": split.get("focus"),
            "exercises": split.get("exercises", []),
            "is_rest_day": split.get("is_rest_day", False),
        }
    except Exception:
        pass

    # Last logged weight per exercise (workout_logs, last 30 days)
    since_30 = (datetime.utcnow() - timedelta(days=30)).date()
    wl_result = await session.execute(
        select(WorkoutLog)
        .where(and_(WorkoutLog.user_id == user.id, WorkoutLog.logged_date >= since_30))
        .order_by(WorkoutLog.logged_date.desc(), WorkoutLog.created_at.desc())
    )
    last_weights: dict = {}
    for row in wl_result.scalars().all():
        if row.exercise not in last_weights:
            last_weights[row.exercise] = {
                "exercise": row.exercise,
                "weight_kg": row.weight_kg,
                "sets": row.sets,
                "reps": row.reps,
                "date": row.logged_date.isoformat(),
            }

    return {
        "date": today.isoformat(),
        "supplements": supplements,
        "fitness": fitness,
        "macros": macros,
        "last_weights": list(last_weights.values()),
    }


@router.get("/admin/errors")
async def get_error_log(
    limit: int = Query(50, ge=1, le=500),
    level: Optional[str] = Query(None),
    user: User = Depends(get_current_user),
    _session: AsyncSession = Depends(get_db),
) -> dict:
    """Return recent structured error log entries (admin/debug use)."""
    from bot.core.monitoring import get_recent_errors
    errors = get_recent_errors(limit=limit, level=level)
    return {"errors": errors, "count": len(errors)}


@router.get("/admin/kill-switches")
async def get_kill_switches(
    user: User = Depends(get_current_user),
) -> dict:
    """Return current state of all automation kill switches."""
    from bot.core.kill_switches import status
    return status()


class KillSwitchBody(BaseModel):
    switch: str
    enabled: bool


class OKRDraftRequest(BaseModel):
    source_text: str
    horizon_weeks: int = 4

    @field_validator("source_text", mode="before")
    @classmethod
    def _strip_source_text(cls, value: str) -> str:
        return (value or "").strip()


class OKRDraftResponse(BaseModel):
    draft: OKRDraft


class ProposalDraftCreateRequest(BaseModel):
    source_text: str
    draft_payload: dict

    @field_validator("source_text", mode="before")
    @classmethod
    def _strip_source_text(cls, value: str) -> str:
        return (value or "").strip()


class ProposalDraftResponse(BaseModel):
    id: int
    source_text: str
    draft_payload: dict
    status: str
    created_at: str


class ProposalDraftReviewRequest(BaseModel):
    action: str  # accept | modify | reject
    source_text: Optional[str] = None
    draft_payload: Optional[dict] = None


@router.post("/admin/kill-switches")
async def set_kill_switch(
    body: KillSwitchBody,
    user: User = Depends(get_current_user),
) -> dict:
    """Enable or disable an automation kill switch."""
    from bot.core.kill_switches import enable, disable, status, _DEFAULTS
    if body.switch not in _DEFAULTS:
        raise HTTPException(status_code=400, detail=f"Unknown switch '{body.switch}'. Valid: {list(_DEFAULTS)}")
    if body.enabled:
        enable(body.switch)
    else:
        disable(body.switch)
    return {"ok": True, **status()}


@router.post("/objectives/okr-draft", response_model=OKRDraftResponse)
async def generate_objective_okr_draft(
    body: OKRDraftRequest,
    user: User = Depends(get_current_user),
) -> OKRDraftResponse:
    """Generate read-only objective draft payload from free-form text (fallback-only)."""
    text = body.source_text
    if not text:
        raise HTTPException(status_code=400, detail="source_text is required")
    if len(text) > 4000:
        raise HTTPException(status_code=400, detail="source_text too long (max 4000 chars)")

    if body.horizon_weeks < 1 or body.horizon_weeks > 52:
        raise HTTPException(status_code=400, detail="horizon_weeks must be between 1 and 52")

    draft = generate_okr_draft_fallback(source_text=text, horizon_weeks=body.horizon_weeks)
    return OKRDraftResponse(draft=draft)


@router.get("/objectives/proposal-drafts", response_model=list[ProposalDraftResponse])
async def list_proposal_drafts(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[ProposalDraftResponse]:
    """List persisted proposal drafts for current user (newest first)."""
    result = await session.execute(
        select(OKRProposalDraft)
        .where(OKRProposalDraft.user_id == user.id)
        .order_by(OKRProposalDraft.id.desc())
        .limit(200)
    )
    rows = result.scalars().all()
    return [
        ProposalDraftResponse(
            id=row.id,
            source_text=row.source_text,
            draft_payload=row.draft_payload,
            status=row.status,
            created_at=row.created_at.isoformat() if row.created_at else datetime.utcnow().isoformat(),
        )
        for row in rows
    ]


@router.post("/objectives/proposal-drafts", response_model=ProposalDraftResponse)
async def create_proposal_draft(
    body: ProposalDraftCreateRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ProposalDraftResponse:
    """Create a persisted proposal draft (draft status only)."""
    if not body.source_text:
        raise HTTPException(status_code=400, detail="source_text is required")

    row = OKRProposalDraft(
        user_id=user.id,
        source_text=body.source_text,
        draft_payload=body.draft_payload,
        status="draft",
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)

    return ProposalDraftResponse(
        id=row.id,
        source_text=row.source_text,
        draft_payload=row.draft_payload,
        status=row.status,
        created_at=row.created_at.isoformat() if row.created_at else datetime.utcnow().isoformat(),
    )


@router.get("/objectives/proposal-drafts/{draft_id}", response_model=ProposalDraftResponse)
async def get_proposal_draft(
    draft_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ProposalDraftResponse:
    """Fetch one persisted proposal draft for current user."""
    result = await session.execute(
        select(OKRProposalDraft).where(
            and_(OKRProposalDraft.id == draft_id, OKRProposalDraft.user_id == user.id)
        )
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="proposal draft not found")

    return ProposalDraftResponse(
        id=row.id,
        source_text=row.source_text,
        draft_payload=row.draft_payload,
        status=row.status,
        created_at=row.created_at.isoformat() if row.created_at else datetime.utcnow().isoformat(),
    )


@router.post("/objectives/proposal-drafts/{draft_id}/review", response_model=ProposalDraftResponse)
async def review_proposal_draft(
    draft_id: int,
    body: ProposalDraftReviewRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ProposalDraftResponse:
    """Review flow skeleton: status transitions only, no downstream execution side-effects."""
    result = await session.execute(
        select(OKRProposalDraft).where(
            and_(OKRProposalDraft.id == draft_id, OKRProposalDraft.user_id == user.id)
        )
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="proposal draft not found")

    action = (body.action or "").strip().lower()
    if action not in {"accept", "modify", "reject"}:
        raise HTTPException(status_code=400, detail="action must be one of: accept, modify, reject")

    if action == "accept":
        row.status = "accepted"
    elif action == "reject":
        row.status = "rejected"
    else:
        row.status = "draft"
        if body.source_text is not None:
            row.source_text = body.source_text.strip()
        if body.draft_payload is not None:
            row.draft_payload = body.draft_payload

    await session.commit()
    await session.refresh(row)

    return ProposalDraftResponse(
        id=row.id,
        source_text=row.source_text,
        draft_payload=row.draft_payload,
        status=row.status,
        created_at=row.created_at.isoformat() if row.created_at else datetime.utcnow().isoformat(),
    )


async def _require_accepted_draft(draft_id: int, user_id: int, session: AsyncSession) -> OKRProposalDraft:
    """Approval gate guard: raises 403 unless draft status is 'accepted'."""
    result = await session.execute(
        select(OKRProposalDraft).where(
            and_(OKRProposalDraft.id == draft_id, OKRProposalDraft.user_id == user_id)
        )
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="proposal draft not found")
    if row.status != "accepted":
        raise HTTPException(
            status_code=403,
            detail=f"proposal draft must be accepted before execution (current status: {row.status})",
        )
    return row


@router.post("/objectives/proposal-drafts/{draft_id}/execute")
async def execute_proposal_draft(
    draft_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Execute an accepted proposal draft into real DB objects.

    Side-effects (Option B):
    - Objective + KeyResults + Tasks
    - Calendar blocks (CalendarEvent) from slot candidates
    - Scheduled reminders (ScheduledReminder) from reminder drafts
    """
    row = await _require_accepted_draft(draft_id, user.id, session)

    from bot.core.proposal_execute import execute_accepted_proposal

    result = await execute_accepted_proposal(session, row)
    return {
        "ok": True,
        "draft_id": draft_id,
        "status": "executed",
        "created": {
            "objective_id": result.objective_id,
            "key_result_ids": result.key_result_ids,
            "task_ids": result.task_ids,
            "calendar_event_ids": result.calendar_event_ids,
            "scheduled_reminder_ids": result.scheduled_reminder_ids,
        },
        "calendar_conflicts": result.calendar_conflicts,
    }


@router.delete("/objectives/proposal-drafts/{draft_id}")
async def delete_proposal_draft(
    draft_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Delete a proposal draft."""
    res = await session.execute(
        select(OKRProposalDraft).where(and_(
            OKRProposalDraft.id == draft_id,
            OKRProposalDraft.user_id == user.id,
        ))
    )
    draft = res.scalar_one_or_none()
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    await session.delete(draft)
    await session.flush()
    return {"ok": True, "deleted_id": draft_id}


@router.get("/objectives/proposal-drafts/{draft_id}/slot-candidates")
async def preview_proposal_draft_slot_candidates(
    draft_id: int,
    horizon_days: int = Query(90, ge=1, le=365),
    include_conflicts: bool = Query(True),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Preview read-only slot candidates derived from an accepted proposal draft."""
    row = await _require_accepted_draft(draft_id, user.id, session)
    candidates = derive_slot_candidates(row.draft_payload, horizon_days=horizon_days)

    conflict_items = []
    if include_conflicts and candidates:
        events_result = await session.execute(
            select(CalendarEvent)
            .where(CalendarEvent.user_id == user.id)
            .order_by(CalendarEvent.start_time)
        )
        existing_events = events_result.scalars().all()
        conflict_items = detect_conflicts(candidates, existing_events)

    return {
        "draft_id": draft_id,
        "status": row.status,
        "count": len(candidates),
        "slot_candidates": [
            {
                "title": c.title,
                "starts_at": c.starts_at.isoformat(),
                "ends_at": c.ends_at.isoformat(),
                "slot_type": c.slot_type,
                "notes": c.notes,
                "source_objective": c.source_objective,
                "source_key_result": c.source_key_result,
                "has_conflict": (
                    any(item.candidate.starts_at == c.starts_at and item.candidate.ends_at == c.ends_at and item.has_conflict for item in conflict_items)
                    if include_conflicts else False
                ),
            }
            for c in candidates
        ],
    }


@router.get("/objectives/proposal-drafts/{draft_id}/reminder-drafts")
async def preview_proposal_draft_reminder_drafts(
    draft_id: int,
    horizon_days: int = Query(30, ge=1, le=90),
    preferred_hour: int = Query(9, ge=0, le=23),
    quiet_hour_start: int = Query(22, ge=0, le=23),
    quiet_hour_end: int = Query(8, ge=0, le=23),
    max_per_day: int = Query(3, ge=1, le=10),
    min_interval_hours: int = Query(4, ge=1, le=24),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Preview read-only reminder drafts derived from an accepted proposal draft."""
    row = await _require_accepted_draft(draft_id, user.id, session)

    config = ReminderConfig(
        horizon_days=horizon_days,
        preferred_hour=preferred_hour,
        quiet_hour_start=quiet_hour_start,
        quiet_hour_end=quiet_hour_end,
        max_per_day=max_per_day,
        min_interval_hours=min_interval_hours,
    )

    drafts = generate_reminder_drafts(row.draft_payload, config=config)

    return {
        "draft_id": draft_id,
        "status": row.status,
        "config": config.model_dump(),
        "count": len(drafts),
        "reminder_drafts": [
            {
                "kind": d.kind,
                "title": d.title,
                "body": d.body,
                "scheduled_at": d.scheduled_at.isoformat(),
                "scheduled_time_local": d.scheduled_time_local,
                "cron": d.cron,
                "priority": d.priority,
                "quiet_hours_respected": d.quiet_hours_respected,
                "max_per_day_bucket": d.max_per_day_bucket,
                "source_objective": d.source_objective,
                "source_key_result": d.source_key_result,
                "frequency": d.frequency,
                "anti_spam_adjusted": d.anti_spam_adjusted,
            }
            for d in drafts
        ],
    }


@router.get("/reminders/due-preview")
async def due_reminders_preview(
    now: Optional[str] = Query(None, description="ISO datetime; defaults to utcnow()"),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Preview what the reminder engine would send *right now* (read-only)."""
    effective_now = datetime.utcnow() if not now else datetime.fromisoformat(now)

    result = await dry_run_preview(session=session, user_id=user.id, now=effective_now)

    # dataclasses → dict
    payload = dataclasses.asdict(result)
    # ensure datetimes are JSON-serializable
    payload["now"] = result.now.isoformat()
    payload["would_send"] = [
        {
            **{k: v for k, v in dataclasses.asdict(r).items() if k not in {"scheduled_for"}},
            "scheduled_for": r.scheduled_for.isoformat(),
        }
        for r in result.would_send
    ]
    return payload


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

    # Bulk-load all relations for this user's objectives in one query.
    obj_ids = [o.id for o in objectives]
    obj_relations: dict[int, list[dict]] = defaultdict(list)
    if obj_ids:
        rel_res = await session.execute(
            select(NodeRelation).where(
                NodeRelation.user_id == user.id,
                or_(
                    and_(NodeRelation.from_type == "objective", NodeRelation.from_id.in_(obj_ids)),
                    and_(NodeRelation.to_type == "objective", NodeRelation.to_id.in_(obj_ids)),
                ),
            )
        )
        for rel in rel_res.scalars().all():
            row = {
                "id": rel.id,
                "relation_type": rel.relation_type,
                "from_type": rel.from_type,
                "from_id": rel.from_id,
                "to_type": rel.to_type,
                "to_id": rel.to_id,
                "note": rel.note,
                "created_at": rel.created_at.isoformat(),
            }
            if rel.from_type == "objective":
                obj_relations[rel.from_id].append(row)
            if rel.to_type == "objective":
                obj_relations[rel.to_id].append(row)

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
                "relations": obj_relations.get(o.id, []),
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
                        "key_result_id": t.key_result_id,
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
            selectinload(Task.blocked_by),
            selectinload(Task.sub_tasks),
            selectinload(Task.calendar_events),
        )
        .where(and_(*conditions))
        .order_by(Task.priority.asc(), Task.due_date.asc().nulls_last())
    )
    tasks = result.scalars().all()
    today = date.today()
    now = datetime.utcnow()

    def _is_unblocked(t: Task) -> bool:
        if not t.blocked_by_task_id:
            return True
        blocker = t.blocked_by
        return blocker is None or blocker.status in ("done", "cancelled")

    def _next_event(t: Task):
        upcoming = [ce for ce in t.calendar_events if ce.start_time >= now]
        if not upcoming:
            return None
        return min(upcoming, key=lambda ce: ce.start_time)

    # Bulk-load all node_relations touching these tasks in one query.
    task_ids = [t.id for t in tasks]
    task_relations: dict[int, list[dict]] = defaultdict(list)
    if task_ids:
        rel_res = await session.execute(
            select(NodeRelation).where(
                NodeRelation.user_id == user.id,
                or_(
                    and_(NodeRelation.from_type == "task", NodeRelation.from_id.in_(task_ids)),
                    and_(NodeRelation.to_type == "task", NodeRelation.to_id.in_(task_ids)),
                ),
            )
        )
        for rel in rel_res.scalars().all():
            row = {
                "id": rel.id,
                "relation_type": rel.relation_type,
                "from_type": rel.from_type,
                "from_id": rel.from_id,
                "to_type": rel.to_type,
                "to_id": rel.to_id,
                "note": rel.note,
                "created_at": rel.created_at.isoformat(),
            }
            if rel.from_type == "task":
                task_relations[rel.from_id].append(row)
            if rel.to_type == "task":
                task_relations[rel.to_id].append(row)

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
                "blocker_title": t.blocked_by.title if t.blocked_by else None,
                "is_unblocked": _is_unblocked(t),
                "subtask_count": len(t.sub_tasks),
                "key_result_title": t.key_result.title if t.key_result else None,
                "objective_title": (
                    t.objective.title if t.objective
                    else (t.key_result.objective.title if t.key_result and t.key_result.objective else None)
                ),
                "created_at": t.created_at.isoformat(),
                "linked_event_id": _next_event(t).id if _next_event(t) else None,
                "linked_event_title": _next_event(t).title if _next_event(t) else None,
                "linked_event_start": _localize_berlin(_next_event(t).start_time) if _next_event(t) else None,
                "relations": task_relations.get(t.id, []),
            }
            for t in tasks
        ]
    }


@router.get("/tasks/dependency-graph")
async def task_dependency_graph(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Return dependency graph (nodes + edges) for all active tasks."""
    result = await session.execute(
        select(Task)
        .options(selectinload(Task.sub_tasks))
        .where(
            Task.user_id == user.id,
            Task.status.in_(["todo", "in_progress"]),
        )
    )
    tasks = result.scalars().all()

    nodes = [
        {
            "id": t.id,
            "title": t.title,
            "status": t.status,
            "priority": t.priority,
            "is_unblocked": (
                not t.blocked_by_task_id
                or not any(t2.id == t.blocked_by_task_id for t2 in tasks)
            ),
        }
        for t in tasks
    ]

    edges = []
    for t in tasks:
        if t.blocked_by_task_id:
            edges.append({
                "from": t.blocked_by_task_id,
                "to": t.id,
                "type": "blocks",
            })
        if t.parent_task_id:
            edges.append({
                "from": t.parent_task_id,
                "to": t.id,
                "type": "parent",
            })

    return {"nodes": nodes, "edges": edges}


# ─── Epic 1.1 — Dependency Graph Relation Endpoints ──────────────────────────

class _CreateNodeRelationBody(BaseModel):
    from_type: str
    from_id: int
    to_type: str
    to_id: int
    relation_type: str
    note: Optional[str] = None

    @field_validator("from_type", "to_type")
    @classmethod
    def validate_node_type(cls, v: str) -> str:
        if v not in VALID_NODE_TYPES:
            raise ValueError(f"node_type must be one of {sorted(VALID_NODE_TYPES)}")
        return v

    @field_validator("relation_type")
    @classmethod
    def validate_relation_type(cls, v: str) -> str:
        if v not in VALID_RELATION_TYPES:
            raise ValueError(f"relation_type must be one of {sorted(VALID_RELATION_TYPES)}")
        return v


def _serialize_relation(rel: NodeRelation) -> dict:
    return {
        "id": rel.id,
        "relation_type": rel.relation_type,
        "from_type": rel.from_type,
        "from_id": rel.from_id,
        "to_type": rel.to_type,
        "to_id": rel.to_id,
        "note": rel.note,
        "created_at": rel.created_at.isoformat(),
    }


@router.get("/relations")
async def list_relations(
    from_type: Optional[str] = Query(None),
    from_id: Optional[int] = Query(None),
    to_type: Optional[str] = Query(None),
    to_id: Optional[int] = Query(None),
    relation_type: Optional[str] = Query(None),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """List all dependency graph relations for the current user, with optional filters."""
    conditions = [NodeRelation.user_id == user.id]
    if from_type:
        conditions.append(NodeRelation.from_type == from_type)
    if from_id is not None:
        conditions.append(NodeRelation.from_id == from_id)
    if to_type:
        conditions.append(NodeRelation.to_type == to_type)
    if to_id is not None:
        conditions.append(NodeRelation.to_id == to_id)
    if relation_type:
        conditions.append(NodeRelation.relation_type == relation_type)
    result = await session.execute(
        select(NodeRelation).where(and_(*conditions)).order_by(NodeRelation.created_at)
    )
    relations = result.scalars().all()
    return {"relations": [_serialize_relation(r) for r in relations]}


@router.post("/relations")
async def create_relation(
    body: _CreateNodeRelationBody,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Create a new dependency graph relation between two nodes."""
    if body.from_type == body.to_type and body.from_id == body.to_id:
        raise HTTPException(status_code=400, detail="A node cannot relate to itself.")
    rel = NodeRelation(
        user_id=user.id,
        from_type=body.from_type,
        from_id=body.from_id,
        to_type=body.to_type,
        to_id=body.to_id,
        relation_type=body.relation_type,
        note=body.note,
    )
    session.add(rel)
    try:
        await session.commit()
        await session.refresh(rel)
    except Exception:
        await session.rollback()
        raise HTTPException(status_code=409, detail="This relation already exists.")
    return {"ok": True, "relation": _serialize_relation(rel)}


@router.delete("/relations/{relation_id}")
async def delete_relation(
    relation_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Delete a dependency graph relation by ID."""
    result = await session.execute(
        select(NodeRelation).where(
            NodeRelation.id == relation_id,
            NodeRelation.user_id == user.id,
        )
    )
    rel = result.scalar_one_or_none()
    if not rel:
        raise HTTPException(status_code=404, detail="Relation not found.")
    await session.delete(rel)
    await session.commit()
    return {"ok": True, "deleted_id": relation_id}


@router.get("/nodes/{node_type}/{node_id}/relations")
async def get_node_relations(
    node_type: str,
    node_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Get all relations where the given node appears as source or target."""
    if node_type not in VALID_NODE_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"node_type must be one of {sorted(VALID_NODE_TYPES)}",
        )
    result = await session.execute(
        select(NodeRelation).where(
            NodeRelation.user_id == user.id,
            or_(
                and_(NodeRelation.from_type == node_type, NodeRelation.from_id == node_id),
                and_(NodeRelation.to_type == node_type, NodeRelation.to_id == node_id),
            ),
        ).order_by(NodeRelation.created_at)
    )
    relations = result.scalars().all()

    outgoing = [r for r in relations if r.from_type == node_type and r.from_id == node_id]
    incoming = [r for r in relations if r.to_type == node_type and r.to_id == node_id]

    return {
        "node_type": node_type,
        "node_id": node_id,
        "outgoing": [_serialize_relation(r) for r in outgoing],
        "incoming": [_serialize_relation(r) for r in incoming],
        "total": len(relations),
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


# ─── Shopping Defaults Endpoints ──────────────────────────────────────────────

class _CreateShoppingDefaultBody(BaseModel):
    title: str
    category: Optional[str] = None


@router.get("/shopping/defaults")
async def list_shopping_defaults(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Get all shopping defaults for the user."""
    result = await session.execute(
        select(ShoppingDefault)
        .where(ShoppingDefault.user_id == user.id)
        .order_by(ShoppingDefault.category.nulls_last(), ShoppingDefault.title)
    )
    defaults = result.scalars().all()
    return {
        "defaults": [
            {
                "id": d.id,
                "title": d.title,
                "category": d.category,
                "active": d.active,
                "created_at": d.created_at.isoformat(),
            }
            for d in defaults
        ]
    }


@router.post("/shopping/defaults")
async def create_shopping_default_api(
    body: _CreateShoppingDefaultBody,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Create a new shopping default item."""
    sd = ShoppingDefault(
        user_id=user.id,
        title=body.title,
        category=body.category,
        active=True,
    )
    session.add(sd)
    await session.flush()
    return {"ok": True, "id": sd.id, "title": sd.title, "category": sd.category}


@router.post("/shopping/load-defaults")
async def load_shopping_defaults_api(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Load all active shopping defaults as tasks into the shopping list."""
    defaults_result = await session.execute(
        select(ShoppingDefault).where(
            and_(ShoppingDefault.user_id == user.id, ShoppingDefault.active == True)  # noqa: E712
        )
    )
    defaults = defaults_result.scalars().all()

    if not defaults:
        return {"ok": True, "added": 0, "items": []}

    existing_result = await session.execute(
        select(Task).where(and_(
            Task.user_id == user.id,
            Task.category == "shopping",
            Task.status.in_(["todo", "in_progress"]),
        ))
    )
    existing_titles = {t.title.lower() for t in existing_result.scalars().all()}

    added = []
    for d in defaults:
        if d.title.lower() not in existing_titles:
            task = Task(
                user_id=user.id,
                title=d.title,
                category="shopping",
                priority=3,
            )
            session.add(task)
            added.append({"title": d.title, "category": d.category})

    await session.flush()
    return {"ok": True, "added": len(added), "items": added}


@router.delete("/shopping/defaults/{default_id}")
async def delete_shopping_default(
    default_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Delete a shopping default."""
    result = await session.execute(
        select(ShoppingDefault).where(and_(
            ShoppingDefault.id == default_id,
            ShoppingDefault.user_id == user.id,
        ))
    )
    sd = result.scalar_one_or_none()
    if not sd:
        raise HTTPException(status_code=404, detail="Shopping default not found")
    await session.delete(sd)
    await session.flush()
    return {"ok": True, "deleted_id": default_id}


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
    """Get routines with today's completion status and impact summary."""
    routines = await get_active_routines(session, user.id)
    completed_today = await get_todays_completions(session, user.id)

    # Load impact rows with objective titles in one query
    routine_ids = [r.id for r in routines]
    impact_map: dict[int, list[dict]] = {r.id: [] for r in routines}
    if routine_ids:
        impact_rows = await session.execute(
            select(RoutineObjectiveImpact, Objective.title)
            .join(Objective, Objective.id == RoutineObjectiveImpact.objective_id)
            .where(
                RoutineObjectiveImpact.user_id == user.id,
                RoutineObjectiveImpact.routine_id.in_(routine_ids),
            )
            .order_by(RoutineObjectiveImpact.impact_score.desc())
        )
        for roi, obj_title in impact_rows:
            impact_map[roi.routine_id].append({
                "objective_id": roi.objective_id,
                "objective_title": obj_title,
                "impact_score": roi.impact_score,
            })

    routines_sorted = sorted(routines, key=lambda r: (r.sort_order, r.id))
    return {
        "routines": [
            {
                "id": r.id,
                "title": r.title,
                "description": r.description,
                "schedule_cron": r.schedule_cron,
                "frequency_human": r.frequency_human,
                "status": r.status,
                "time_of_day": r.time_of_day or "anytime",
                "sort_order": r.sort_order or 0,
                "completed_today": r.id in completed_today,
                "objective_impacts": impact_map[r.id],
            }
            for r in routines_sorted
        ]
    }


def _localize_berlin(dt: datetime) -> str:
    """Convert naive-UTC datetime to Europe/Berlin for correct frontend display."""
    from zoneinfo import ZoneInfo
    if dt.tzinfo is not None:
        return dt.astimezone(ZoneInfo("Europe/Berlin")).isoformat()
    # Naive datetimes in DB are UTC — convert to Berlin
    return dt.replace(tzinfo=ZoneInfo("UTC")).astimezone(ZoneInfo("Europe/Berlin")).isoformat()


def _event_dict(e: CalendarEvent) -> dict:
    return {
        "id": e.id,
        "title": e.title,
        "description": e.description,
        "start_time": _localize_berlin(e.start_time),
        "end_time": _localize_berlin(e.end_time) if e.end_time else None,
        "all_day": e.all_day,
        "event_type": e.event_type,
        "notes": e.description,
        "linked_task_id": e.linked_task_id,
        "linked_task_title": e.linked_task.title if e.linked_task else None,
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
        .options(selectinload(CalendarEvent.linked_task))
        .where(and_(
            CalendarEvent.user_id == user.id,
            CalendarEvent.start_time >= start,
            CalendarEvent.start_time <= end,
        ))
        .order_by(CalendarEvent.start_time)
    )
    events = result.scalars().all()
    return {"events": [_event_dict(e) for e in events]}


class CalendarEventCreate(BaseModel):
    title: str
    start_time: str
    end_time: Optional[str] = None
    event_type: Optional[str] = "reminder"
    all_day: Optional[bool] = False
    description: Optional[str] = None
    linked_task_id: Optional[int] = None
    linked_routine_id: Optional[int] = None


@router.post("/calendar")
async def create_calendar_event_api(
    body: CalendarEventCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Create a new calendar event via API."""
    from bot.core.calendar import create_calendar_event
    event = await create_calendar_event(
        session,
        user_id=user.id,
        title=body.title,
        start_time=body.start_time,
        event_type=body.event_type or "reminder",
        end_time=body.end_time,
        all_day=body.all_day or False,
        description=body.description,
        linked_task_id=body.linked_task_id,
        linked_routine_id=body.linked_routine_id,
    )
    await session.refresh(event, ["linked_task"])
    return _event_dict(event)


class CalendarEventUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    all_day: Optional[bool] = None
    event_type: Optional[str] = None
    linked_task_id: Optional[int] = None


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
        select(CalendarEvent)
        .options(selectinload(CalendarEvent.linked_task))
        .where(
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
    if body.linked_task_id is not None:
        # verify task belongs to user
        task_res = await session.execute(
            select(Task).where(Task.id == body.linked_task_id, Task.user_id == user.id)
        )
        if not task_res.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Task nicht gefunden")
        event.linked_task_id = body.linked_task_id
    from bot.core.calendar import _berlin_to_utc
    _time_fmts = ["%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M", "%Y-%m-%d"]
    new_start = event.start_time
    new_end = event.end_time
    if body.start_time is not None:
        for fmt in _time_fmts:
            try:
                new_start = _berlin_to_utc(datetime.strptime(body.start_time, fmt))
                break
            except ValueError:
                continue
    if body.end_time is not None:
        for fmt in _time_fmts:
            try:
                new_end = _berlin_to_utc(datetime.strptime(body.end_time, fmt))
                break
            except ValueError:
                continue
    if new_start is not None and new_end is not None and new_end <= new_start:
        raise HTTPException(status_code=422, detail="end_time must be after start_time")
    if body.start_time is not None:
        event.start_time = new_start
    if body.end_time is not None:
        event.end_time = new_end

    await session.flush()
    await session.refresh(event, ["linked_task"])
    return _event_dict(event)


class CalendarRescheduleBody(BaseModel):
    start_time: str
    end_time: Optional[str] = None


@router.patch("/calendar/{event_id}/reschedule")
async def reschedule_calendar_event(
    event_id: int,
    body: CalendarRescheduleBody,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Reschedule a calendar event: update start/end times with validation."""
    result = await session.execute(
        select(CalendarEvent)
        .options(selectinload(CalendarEvent.linked_task))
        .where(
            CalendarEvent.id == event_id,
            CalendarEvent.user_id == user.id,
        )
    )
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    from bot.core.calendar import _berlin_to_utc
    _time_fmts = ["%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M", "%Y-%m-%d"]
    new_start: Optional[datetime] = None
    for fmt in _time_fmts:
        try:
            new_start = _berlin_to_utc(datetime.strptime(body.start_time, fmt))
            break
        except ValueError:
            continue
    if new_start is None:
        raise HTTPException(status_code=422, detail="Invalid start_time format")

    new_end: Optional[datetime] = None
    if body.end_time is not None:
        for fmt in _time_fmts:
            try:
                new_end = _berlin_to_utc(datetime.strptime(body.end_time, fmt))
                break
            except ValueError:
                continue
        if new_end is None:
            raise HTTPException(status_code=422, detail="Invalid end_time format")
        if new_end <= new_start:
            raise HTTPException(status_code=422, detail="end_time must be after start_time")

    event.start_time = new_start
    if new_end is not None:
        event.end_time = new_end

    await session.flush()
    await session.refresh(event, ["linked_task"])
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
        select(CalendarEvent)
        .options(selectinload(CalendarEvent.linked_task))
        .where(
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


@router.delete("/calendar/{event_id}")
async def delete_calendar_event(
    event_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Delete a calendar event."""
    result = await session.execute(
        select(CalendarEvent).where(
            CalendarEvent.id == event_id,
            CalendarEvent.user_id == user.id,
        )
    )
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Event nicht gefunden")
    await session.delete(event)
    await session.flush()
    return {"ok": True, "deleted_id": event_id}


class CalendarLinkTaskBody(BaseModel):
    task_id: Optional[int] = None  # null to detach


@router.post("/calendar/{event_id}/link-task")
async def link_calendar_task(
    event_id: int,
    body: CalendarLinkTaskBody,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Attach or detach a task from a calendar event. Pass task_id=null to detach."""
    result = await session.execute(
        select(CalendarEvent)
        .options(selectinload(CalendarEvent.linked_task))
        .where(CalendarEvent.id == event_id, CalendarEvent.user_id == user.id)
    )
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Event nicht gefunden")

    if body.task_id is None:
        event.linked_task_id = None
    else:
        task_res = await session.execute(
            select(Task).where(Task.id == body.task_id, Task.user_id == user.id)
        )
        task = task_res.scalar_one_or_none()
        if not task:
            raise HTTPException(status_code=404, detail="Task nicht gefunden")
        event.linked_task_id = body.task_id

    await session.flush()
    await session.refresh(event, ["linked_task"])
    return _event_dict(event)


class ShiftRoutinesBody(BaseModel):
    weekday: int        # 0=Mon … 6=Sun
    target_hour: int    # desired local (Berlin) hour for the first routine


BERLIN_TZ = ZoneInfo("Europe/Berlin")


@router.post("/calendar/shift-routines")
async def shift_day_routines(
    body: ShiftRoutinesBody,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Align all morning Routine events on a weekday so the earliest one
    starts at target_hour (Berlin time).  Calculates delta from actual DB
    times so it always works regardless of what was saved before."""
    now = datetime.utcnow()
    iso_dow = body.weekday + 1  # Mon=1 … Sun=7

    result = await session.execute(
        select(CalendarEvent)
        .where(
            CalendarEvent.user_id == user.id,
            CalendarEvent.event_type == "routine",
            CalendarEvent.start_time >= now,
            extract("hour", CalendarEvent.start_time) < 14,
            extract("isodow", CalendarEvent.start_time) == iso_dow,
        )
        .order_by(CalendarEvent.start_time)
    )
    events = result.scalars().all()
    if not events:
        return {"shifted": 0}

    # Determine current local hour of the earliest routine
    first_utc = events[0].start_time.replace(tzinfo=timezone.utc)
    first_local = first_utc.astimezone(BERLIN_TZ)
    current_minutes = first_local.hour * 60 + first_local.minute
    target_minutes = body.target_hour * 60
    delta = timedelta(minutes=target_minutes - current_minutes)

    if delta.total_seconds() == 0:
        return {"shifted": 0}

    for e in events:
        e.start_time = e.start_time + delta
        if e.end_time:
            e.end_time = e.end_time + delta
    await session.commit()
    return {"shifted": len(events)}


@router.delete("/calendar/{event_id}/link-task")
async def unlink_calendar_task(
    event_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Remove the task linkage from a calendar event."""
    result = await session.execute(
        select(CalendarEvent)
        .options(selectinload(CalendarEvent.linked_task))
        .where(CalendarEvent.id == event_id, CalendarEvent.user_id == user.id)
    )
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Event nicht gefunden")

    event.linked_task_id = None
    await session.flush()
    await session.refresh(event, ["linked_task"])
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


class _CreateBrainDumpBody(BaseModel):
    raw_input: str


@router.post("/brain-dumps")
async def create_brain_dump(
    body: _CreateBrainDumpBody,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Create a new brain dump and award XP."""
    dump = BrainDump(user_id=user.id, raw_input=body.raw_input)
    session.add(dump)
    await session.flush()

    _, new_level, leveled_up, _ = await _add_xp(user.id, 15, "brain_dump", session)
    if leveled_up:
        await send_message(user.telegram_id, f"⬆️ LEVEL UP! Du bist jetzt Level {new_level}! 🎉")

    return {"ok": True, "id": dump.id, "xp_gained": 15}


class _CreateLogBody(BaseModel):
    log_type: str
    data: dict
    raw_input: Optional[str] = None


@router.post("/logs")
async def create_log(
    body: _CreateLogBody,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Create a new log entry and award XP."""
    log = Log(
        user_id=user.id,
        log_type=body.log_type,
        data=body.data,
        source="dashboard",
        raw_input=body.raw_input,
    )
    session.add(log)
    await session.flush()

    _, new_level, leveled_up, _ = await _add_xp(user.id, 5, "log_created", session)
    if leveled_up:
        await send_message(user.telegram_id, f"⬆️ LEVEL UP! Du bist jetzt Level {new_level}! 🎉")

    return {"ok": True, "id": log.id, "xp_gained": 5}


@router.get("/gamification/stats")
async def get_gamification_stats(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Get XP, level, and recent achievements for the user."""
    total_xp = user.xp or 0
    level = user.level or get_level(total_xp)
    xp_for_current = level * level * 100
    xp_for_next = (level + 1) * (level + 1) * 100

    result = await session.execute(
        select(UserAchievement)
        .options(selectinload(UserAchievement.achievement))
        .where(UserAchievement.user_id == user.id)
        .order_by(UserAchievement.unlocked_at.desc())
        .limit(3)
    )
    recent = result.scalars().all()

    return {
        "xp": total_xp,
        "level": level,
        "level_title": get_level_title(level),
        "xp_progress": max(0, total_xp - xp_for_current),
        "xp_to_next": xp_for_next - xp_for_current,
        "recent_achievements": [
            {
                "id": ua.achievement.id,
                "title": ua.achievement.title,
                "emoji": ua.achievement.emoji,
                "category": ua.achievement.category,
                "xp_reward": ua.achievement.xp_reward,
                "unlocked_at": ua.unlocked_at.isoformat(),
            }
            for ua in recent
        ],
    }


@router.get("/gamification/momentum")
async def get_goal_momentum(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Calculate momentum score per active objective.

    Momentum = (tasks_done_14d * 10) + (has_recent_log * 20) - (days_since_last_activity * 2)
    Capped 0–100. Also returns overall portfolio momentum.
    """
    today = date.today()
    fourteen_ago = datetime.combine(today - timedelta(days=14), datetime.min.time())
    thirty_ago = datetime.combine(today - timedelta(days=30), datetime.min.time())

    obj_res = await session.execute(
        select(Objective).where(and_(
            Objective.user_id == user.id,
            Objective.status == "active",
        ))
    )
    objectives = obj_res.scalars().all()

    momentum_list = []
    for obj in objectives:
        # Tasks done in last 14 days
        tasks_res = await session.execute(
            select(func.count()).select_from(Task).where(and_(
                Task.objective_id == obj.id,
                Task.status == "done",
                Task.completed_at >= fourteen_ago,
            ))
        )
        tasks_done_14d = tasks_res.scalar() or 0

        # Most recent task completion date
        last_task_res = await session.execute(
            select(Task.completed_at).where(and_(
                Task.objective_id == obj.id,
                Task.status == "done",
                Task.completed_at >= thirty_ago,
            ))
            .order_by(Task.completed_at.desc())
            .limit(1)
        )
        last_row = last_task_res.scalar_one_or_none()
        if last_row:
            days_since = (today - last_row.date()).days
        else:
            days_since = 30

        score = min(100, max(0,
            tasks_done_14d * 10
            - days_since * 2
            + (10 if tasks_done_14d > 0 else 0)
        ))

        momentum_list.append({
            "id": obj.id,
            "title": obj.title,
            "category": obj.category,
            "momentum": score,
            "tasks_done_14d": tasks_done_14d,
            "days_since_last_task": days_since,
            "level": "high" if score >= 60 else "medium" if score >= 30 else "low",
        })

    momentum_list.sort(key=lambda x: x["momentum"], reverse=True)
    portfolio_avg = int(sum(m["momentum"] for m in momentum_list) / len(momentum_list)) if momentum_list else 0

    return {
        "objectives": momentum_list,
        "portfolio_momentum": portfolio_avg,
        "portfolio_level": "high" if portfolio_avg >= 60 else "medium" if portfolio_avg >= 30 else "low",
    }


@router.get("/gamification/xp-history")
async def get_xp_history(
    days: int = Query(30, ge=7, le=90),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Return daily XP earned over the last N days.

    XP sources:
    - Completed tasks: 5 XP each (task.completed_at)
    - Unlocked achievements: their xp_reward (user_achievement.unlocked_at)
    """
    cutoff = datetime.combine(date.today() - timedelta(days=days), datetime.min.time())
    today = date.today()

    # Build empty buckets
    xp_by_day: dict[str, int] = {}
    for i in range(days):
        d = (today - timedelta(days=i)).isoformat()
        xp_by_day[d] = 0

    # Tasks completed: 5 XP each
    tasks_res = await session.execute(
        select(Task.completed_at).where(and_(
            Task.user_id == user.id,
            Task.status == "done",
            Task.completed_at >= cutoff,
        ))
    )
    for (completed_at,) in tasks_res.all():
        if completed_at:
            day_key = completed_at.date().isoformat()
            if day_key in xp_by_day:
                xp_by_day[day_key] += 5

    # Achievement unlocks
    ach_res = await session.execute(
        select(UserAchievement.unlocked_at, Achievement.xp_reward)
        .join(Achievement, Achievement.id == UserAchievement.achievement_id)
        .where(and_(
            UserAchievement.user_id == user.id,
            UserAchievement.unlocked_at >= cutoff,
        ))
    )
    for unlocked_at, xp_reward in ach_res.all():
        day_key = unlocked_at.date().isoformat()
        if day_key in xp_by_day:
            xp_by_day[day_key] += xp_reward

    # Return sorted ascending
    history = [{"date": d, "xp": xp_by_day[d]} for d in sorted(xp_by_day)]
    return {"history": history, "days": days, "total_xp": user.xp or 0}


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
    water_today = sum((l.data or {}).get("amount", 0) for l in water_result.scalars().all())

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

    # ── XP / Level (read from stored values) ───────────────────────────────
    total_xp = user.xp or 0
    level = user.level or get_level(total_xp)
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
            "xp_progress": max(0, total_xp - xp_for_current),
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
        d = l.data or {}
        week_key = l.logged_at.strftime("%Y-W%W")
        weight = float(d.get("weight", 0) or 0)
        reps = float(d.get("reps", 1) or 1)
        sets = float(d.get("sets", 1) or 1)
        if weight > 0:
            volume_by_week[week_key] += weight * reps * sets

    sessions_by_day: dict = {}
    for l in workout_logs:
        d = l.data or {}
        day = l.logged_at.date().isoformat()
        if day not in sessions_by_day:
            sessions_by_day[day] = []
        sessions_by_day[day].append({
            "exercise": d.get("exercise", "?"),
            "weight": d.get("weight"),
            "reps": d.get("reps"),
            "sets": d.get("sets"),
            "duration_min": d.get("duration_min"),
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
        d = l.data or {}
        ex = str(d.get("exercise", "Unbekannt")).strip()
        if ex not in exercises:
            exercises[ex] = {
                "name": ex,
                "count": 0,
                "max_weight": 0.0,
                "last_done": l.logged_at.isoformat(),
            }
        exercises[ex]["count"] += 1
        weight = float(d.get("weight", 0) or 0)
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
        d = l.data or {}
        ex = str(d.get("exercise", "Unbekannt")).strip()
        weight = float(d.get("weight", 0) or 0)
        reps = d.get("reps")
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


def _load_fitness_protocol_splits() -> list[dict]:
    """Load splits from the local protocol JSON as a fallback."""
    import json
    from pathlib import Path

    protocol_path = Path(__file__).resolve().parents[2] / "docs" / "protocols" / "lukas_fitness_split.json"
    if not protocol_path.exists():
        return []
    protocol = json.loads(protocol_path.read_text())
    rotation: list[str] = protocol["meta"]["rotation"]
    splits_data: dict = protocol["splits"]
    anchor_str: str = protocol["meta"]["rotation_anchor_date"]

    anchor = date.fromisoformat(anchor_str)
    today = date.today()
    days_elapsed = (today - anchor).days
    today_idx = days_elapsed % len(rotation)
    today_name = rotation[today_idx]

    result = []
    for order, name in enumerate(rotation, start=1):
        split_def = splits_data[name]
        exercises = [{"name": ex} for ex in split_def["exercises"]]
        result.append({
            "id": f"proto-{order}",
            "name": name,
            "exercises": exercises,
            "day_of_week": None,
            "order_in_rotation": order,
            "created_at": anchor_str + "T00:00:00",
            "workout_count": 0,
            "last_used": None,
            "is_next": name == today_name,
        })
    return result


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

    # No splits in DB → fall back to protocol JSON so the page is never empty
    if not splits:
        proto_splits = _load_fitness_protocol_splits()
        next_split_id = next((s["id"] for s in proto_splits if s["is_next"]), None)
        return {"splits": proto_splits, "next_split_id": next_split_id, "from_protocol": True}

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
        sid = (log.data or {}).get("split_id")
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
        "from_protocol": False,
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
    """Mark a task as done from the dashboard. Updates linked KR/objective progress
    and returns the next unblocked action (CORE-7)."""
    from bot.core.completion_hooks import (
        check_objective_auto_complete,
        get_next_unblocked_action,
        update_kr_on_task_complete,
    )

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

    # Auto-complete any action queue item linked to this task
    aq_result = await session.execute(
        select(ActionQueueItem).where(
            and_(
                ActionQueueItem.linked_task_id == task.id,
                ActionQueueItem.user_id == user.id,
                ActionQueueItem.state != "completed",
            )
        )
    )
    linked_queue_item = aq_result.scalar_one_or_none()
    if linked_queue_item:
        linked_queue_item.state = "completed"
        linked_queue_item.updated_at = datetime.utcnow()
    await session.flush()

    # CORE-7: update KR progress
    kr_updated = await update_kr_on_task_complete(session, task)

    # CORE-7: auto-complete objective if all KRs done
    objective_completed = False
    if task.objective_id:
        objective_completed = await check_objective_auto_complete(session, task.objective_id)

    # CORE-7: surface next unblocked action
    next_action = await get_next_unblocked_action(session, user.id, completed_task=task)

    _, new_level, leveled_up, _ = await _add_xp(user.id, 10, "task_complete", session)
    if leveled_up:
        await send_message(user.telegram_id, f"⬆️ LEVEL UP! Du bist jetzt Level {new_level}! 🎉")

    # Push next action to Telegram
    try:
        push_msg = f"✅ *{task.title}* erledigt!"
        if objective_completed:
            push_msg += f"\n\n🎯 Objective abgeschlossen! Großartig!"
        elif next_action:
            action_title = next_action.get("title") or next_action.get("description") or str(next_action)
            push_msg += f"\n\n➡️ *Nächste Aktion:*\n☐ {action_title}"
        else:
            # Find next priority task
            from bot.core.tasks import get_open_tasks
            open_tasks = await get_open_tasks(session, user.id, limit=3)
            remaining = [t for t in open_tasks if t.id != task_id]
            if remaining:
                push_msg += f"\n\n➡️ *Als nächstes:*\n☐ [P{remaining[0].priority}] {remaining[0].title}"
            else:
                push_msg += "\n\n🎉 Alle Tasks erledigt — Zeit für neue Ziele!"
        await send_message(user.telegram_id, push_msg, parse_mode="Markdown")
    except Exception as _push_err:
        logger.warning("Next-action push failed: %s", _push_err)

    response: dict = {"ok": True, "task_id": task_id, "title": task.title, "xp_gained": 10}
    if kr_updated:
        response["kr_progress"] = {
            "id": kr_updated.id,
            "current_value": kr_updated.current_value,
            "target_value": kr_updated.target_value,
            "status": kr_updated.status,
        }
    if objective_completed:
        response["objective_completed"] = task.objective_id
    if next_action:
        response["next_action"] = next_action
    return response


@router.post("/routines/{routine_id}/complete")
async def complete_routine_endpoint(
    routine_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Mark a routine as done for today from the dashboard. Updates linked KR progress
    and returns the next pending routine or top task (CORE-7)."""
    from bot.core.completion_hooks import get_next_unblocked_action, update_kr_on_routine_complete

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

    # CORE-7: update linked KR progress (streak/number)
    kr_updated = await update_kr_on_routine_complete(session, routine)

    # CORE-7: next pending routine (not yet done today) or top unblocked task
    completed_ids_res = await session.execute(
        select(RoutineCompletion.routine_id).where(and_(
            RoutineCompletion.user_id == user.id,
            RoutineCompletion.completed_at >= today_start,
        ))
    )
    done_ids = set(completed_ids_res.scalars().all())
    next_routine_res = await session.execute(
        select(Routine).where(and_(
            Routine.user_id == user.id,
            Routine.status == "active",
            Routine.id.not_in(done_ids) if done_ids else Routine.status == "active",
        ))
        .order_by(Routine.sort_order.asc(), Routine.id.asc())
        .limit(1)
    )
    next_routine = next_routine_res.scalar_one_or_none()

    next_action: Optional[dict] = None
    if next_routine:
        next_action = {
            "type": "routine",
            "id": next_routine.id,
            "title": next_routine.title,
            "time_of_day": next_routine.time_of_day,
        }
    else:
        task_next = await get_next_unblocked_action(session, user.id)
        if task_next:
            next_action = {"type": "task", **task_next}

    _, new_level, leveled_up, _ = await _add_xp(user.id, 5, "routine_complete", session)
    if leveled_up:
        await send_message(user.telegram_id, f"⬆️ LEVEL UP! Du bist jetzt Level {new_level}! 🎉")

    response: dict = {"ok": True, "routine_id": routine_id, "title": routine.title, "xp_gained": 5}
    if kr_updated:
        response["kr_progress"] = {
            "id": kr_updated.id,
            "current_value": kr_updated.current_value,
            "target_value": kr_updated.target_value,
            "status": kr_updated.status,
        }
    if next_action:
        response["next_action"] = next_action
    return response


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


@router.get("/auth/validate")
@router.post("/auth/validate")
async def validate_token(
    user: User = Depends(get_current_user),
) -> dict:
    """Validate Bearer token — returns 200 if valid, 401 if not."""
    return {"valid": True, "user_id": user.id}


@router.post("/auth/token")
async def generate_token(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Regenerate API token for a user."""
    token = await generate_api_token(session, user)
    return {"token": token}


# ─── CRUD: Pydantic request bodies ────────────────────────────────────────────

class CreateObjectiveBody(BaseModel):
    title: str
    category: Optional[str] = "personal"
    description: Optional[str] = None
    target_date: Optional[str] = None
    parent_objective_id: Optional[int] = None


class CreateTaskBody(BaseModel):
    title: str
    category: Optional[str] = None
    priority: Optional[int] = 3
    due_date: Optional[str] = None
    objective_id: Optional[int] = None
    description: Optional[str] = None
    parent_task_id: Optional[int] = None
    blocked_by_task_id: Optional[int] = None


class CreateRoutineBody(BaseModel):
    title: str
    description: Optional[str] = None
    frequency_human: Optional[str] = "Täglich"
    time_of_day: Optional[str] = "morning"


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
    parent_task_id: Optional[int] = None
    blocked_by_task_id: Optional[int] = None


class UpdateRoutineBody(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    frequency_human: Optional[str] = None
    status: Optional[str] = None
    time_of_day: Optional[str] = None
    sort_order: Optional[int] = None


class UpdateBrainDumpBody(BaseModel):
    raw_input: Optional[str] = None


# ─── Objectives CRUD ──────────────────────────────────────────────────────────

@router.post("/objectives")
async def create_objective(
    body: CreateObjectiveBody,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Create a new objective."""
    target = None
    if body.target_date:
        try:
            target = date.fromisoformat(body.target_date)
        except ValueError:
            pass
    obj = Objective(
        user_id=user.id,
        title=body.title.strip(),
        category=body.category or "personal",
        description=body.description or None,
        target_date=target,
        status="active",
        parent_objective_id=body.parent_objective_id or None,
    )
    session.add(obj)
    await session.flush()
    return {"ok": True, "id": obj.id, "title": obj.title}


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


# ─── Key Results CRUD ─────────────────────────────────────────────────────────

class CreateKeyResultBody(BaseModel):
    title: str
    metric_type: Optional[str] = "number"
    target_value: Optional[float] = None
    unit: Optional[str] = None


class UpdateKeyResultBody(BaseModel):
    title: Optional[str] = None
    metric_type: Optional[str] = None
    target_value: Optional[float] = None
    unit: Optional[str] = None
    status: Optional[str] = None


def _kr_dict(kr: KeyResult) -> dict:
    progress = (
        min(100, int((kr.current_value / kr.target_value) * 100))
        if kr.target_value and kr.target_value > 0
        else 0
    )
    return {
        "id": kr.id,
        "title": kr.title,
        "metric_type": kr.metric_type,
        "target_value": kr.target_value,
        "current_value": kr.current_value,
        "unit": kr.unit,
        "frequency": kr.frequency,
        "status": kr.status,
        "progress_pct": progress,
    }


@router.post("/objectives/{objective_id}/key-results")
async def create_key_result(
    objective_id: int,
    body: CreateKeyResultBody,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Add a key result to an objective."""
    obj_res = await session.execute(
        select(Objective).where(and_(Objective.id == objective_id, Objective.user_id == user.id))
    )
    if not obj_res.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Objective not found")
    kr = KeyResult(
        objective_id=objective_id,
        user_id=user.id,
        title=body.title.strip(),
        metric_type=body.metric_type or "number",
        target_value=body.target_value,
        unit=body.unit,
    )
    session.add(kr)
    await session.flush()
    await session.refresh(kr)
    return {"ok": True, **_kr_dict(kr)}


@router.patch("/objectives/{objective_id}/key-results/{kr_id}")
async def update_key_result(
    objective_id: int,
    kr_id: int,
    body: UpdateKeyResultBody,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Update a key result."""
    res = await session.execute(
        select(KeyResult).where(and_(
            KeyResult.id == kr_id,
            KeyResult.objective_id == objective_id,
            KeyResult.user_id == user.id,
        ))
    )
    kr = res.scalar_one_or_none()
    if not kr:
        raise HTTPException(status_code=404, detail="Key result not found")
    if body.title is not None:
        kr.title = body.title.strip()
    if body.metric_type is not None:
        kr.metric_type = body.metric_type
    if body.target_value is not None:
        kr.target_value = body.target_value
    if body.unit is not None:
        kr.unit = body.unit
    if body.status is not None:
        kr.status = body.status
    await session.flush()
    return {"ok": True, **_kr_dict(kr)}


@router.delete("/objectives/{objective_id}/key-results/{kr_id}")
async def delete_key_result(
    objective_id: int,
    kr_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Delete a key result."""
    res = await session.execute(
        select(KeyResult).where(and_(
            KeyResult.id == kr_id,
            KeyResult.objective_id == objective_id,
            KeyResult.user_id == user.id,
        ))
    )
    kr = res.scalar_one_or_none()
    if not kr:
        raise HTTPException(status_code=404, detail="Key result not found")
    await session.delete(kr)
    await session.flush()
    return {"ok": True, "deleted_id": kr_id}


# ─── Tasks CRUD ───────────────────────────────────────────────────────────────

@router.post("/tasks")
async def create_task(
    body: CreateTaskBody,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Create a new task."""
    due = None
    if body.due_date:
        try:
            due = date.fromisoformat(body.due_date)
        except ValueError:
            pass
    task = Task(
        user_id=user.id,
        title=body.title.strip(),
        description=body.description or None,
        category=body.category or None,
        priority=max(1, min(5, body.priority or 3)),
        due_date=due,
        objective_id=body.objective_id or None,
        parent_task_id=body.parent_task_id or None,
        blocked_by_task_id=body.blocked_by_task_id or None,
        status="todo",
    )
    session.add(task)
    await session.flush()
    _, _, leveled_up, _ = await _add_xp(user.id, 5, "task_created", session)
    return {"ok": True, "id": task.id, "title": task.title, "leveled_up": leveled_up}


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
    if body.parent_task_id is not None:
        task.parent_task_id = body.parent_task_id if body.parent_task_id > 0 and body.parent_task_id != task_id else None
    if body.blocked_by_task_id is not None:
        task.blocked_by_task_id = body.blocked_by_task_id if body.blocked_by_task_id > 0 and body.blocked_by_task_id != task_id else None

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

@router.post("/routines")
async def create_routine(
    body: CreateRoutineBody,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Create a new routine."""
    routine = Routine(
        user_id=user.id,
        title=body.title.strip(),
        description=body.description or None,
        frequency_human=body.frequency_human or "Täglich",
        time_of_day=body.time_of_day or "morning",
        status="active",
        sort_order=0,
    )
    session.add(routine)
    await session.flush()
    return {"ok": True, "id": routine.id, "title": routine.title}


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
    if body.time_of_day is not None:
        routine.time_of_day = body.time_of_day
    if body.sort_order is not None:
        routine.sort_order = body.sort_order

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
    timezone: Optional[str] = None


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
    quiet_hour_start: Optional[int] = None
    quiet_hour_end: Optional[int] = None


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
            "quiet_hour_start": s.get("quiet_hour_start", 22),
            "quiet_hour_end": s.get("quiet_hour_end", 8),
        },
        "category_weights": s.get("category_weights", {}),
    }


@router.put("/settings/profile")
async def update_profile(
    body: UpdateProfileBody,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Update user profile (name, timezone)."""
    if body.first_name is not None:
        stripped = body.first_name.strip()
        if stripped:
            user.first_name = stripped
    if body.timezone is not None:
        tz = body.timezone.strip()
        if tz:
            user.timezone = tz
    await session.flush()
    return {"ok": True, "first_name": user.first_name, "timezone": user.timezone}


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
    if body.quiet_hour_start is not None:
        settings["quiet_hour_start"] = max(0, min(23, body.quiet_hour_start))
    if body.quiet_hour_end is not None:
        settings["quiet_hour_end"] = max(0, min(23, body.quiet_hour_end))
    user.settings = settings
    await session.flush()
    return {"ok": True}


@router.get("/settings/export")
async def export_data(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    format: str = Query("json"),
) -> JSONResponse:
    """Export all user data as JSON or CSV download."""
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
                "start_time": _localize_berlin(e.start_time),
                "end_time": _localize_berlin(e.end_time) if e.end_time else None,
                "all_day": e.all_day,
                "event_type": e.event_type,
            }
            for e in calendar_events
        ],
    }

    if format == "csv":
        import csv
        import io
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["id", "title", "status", "priority", "due_date", "objective"])
        obj_map = {o.id: o.title for o in objectives}
        for t in tasks:
            obj_title = obj_map.get(t.objective_id, "") if t.objective_id else ""
            writer.writerow([
                t.id,
                t.title,
                t.status,
                t.priority,
                t.due_date.isoformat() if t.due_date else "",
                obj_title,
            ])
        from fastapi.responses import Response
        return Response(
            content=buf.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=personal-os-tasks.csv"},
        )

    return JSONResponse(
        content=payload,
        headers={"Content-Disposition": f"attachment; filename=personal-os-export.json"},
    )


# ─── Phase B5 — Routine-Objective Impact Scoring ──────────────────────────────

class RoutineImpactUpsert(BaseModel):
    objective_id: int
    impact_score: int = 3  # 1–5
    notes: Optional[str] = None


@router.get("/routines/{routine_id}/impacts")
async def get_routine_impacts(
    routine_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """List all objectives this routine impacts, with scores."""
    rows = await session.execute(
        select(RoutineObjectiveImpact, Objective.title, Objective.status)
        .join(Objective, Objective.id == RoutineObjectiveImpact.objective_id)
        .where(
            RoutineObjectiveImpact.user_id == user.id,
            RoutineObjectiveImpact.routine_id == routine_id,
        )
        .order_by(RoutineObjectiveImpact.impact_score.desc())
    )
    return {
        "routine_id": routine_id,
        "impacts": [
            {
                "objective_id": roi.objective_id,
                "objective_title": obj_title,
                "objective_status": obj_status,
                "impact_score": roi.impact_score,
                "notes": roi.notes,
                "created_at": roi.created_at.isoformat(),
            }
            for roi, obj_title, obj_status in rows
        ],
    }


@router.post("/routines/{routine_id}/impacts")
async def upsert_routine_impact(
    routine_id: int,
    body: RoutineImpactUpsert,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Set or update the impact score for a routine→objective link."""
    if not (1 <= body.impact_score <= 5):
        raise HTTPException(status_code=400, detail="impact_score must be 1–5")

    # Verify routine ownership
    r = await session.get(Routine, routine_id)
    if not r or r.user_id != user.id:
        raise HTTPException(status_code=404, detail="Routine not found")

    # Verify objective ownership
    o = await session.get(Objective, body.objective_id)
    if not o or o.user_id != user.id:
        raise HTTPException(status_code=404, detail="Objective not found")

    existing = await session.execute(
        select(RoutineObjectiveImpact).where(
            RoutineObjectiveImpact.routine_id == routine_id,
            RoutineObjectiveImpact.objective_id == body.objective_id,
        )
    )
    roi = existing.scalar_one_or_none()
    if roi:
        roi.impact_score = body.impact_score
        roi.notes = body.notes
    else:
        roi = RoutineObjectiveImpact(
            user_id=user.id,
            routine_id=routine_id,
            objective_id=body.objective_id,
            impact_score=body.impact_score,
            notes=body.notes,
        )
        session.add(roi)
    await session.flush()
    return {"routine_id": routine_id, "objective_id": body.objective_id, "impact_score": roi.impact_score}


@router.delete("/routines/{routine_id}/impacts/{objective_id}")
async def delete_routine_impact(
    routine_id: int,
    objective_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Remove the impact link between a routine and an objective."""
    result = await session.execute(
        select(RoutineObjectiveImpact).where(
            RoutineObjectiveImpact.user_id == user.id,
            RoutineObjectiveImpact.routine_id == routine_id,
            RoutineObjectiveImpact.objective_id == objective_id,
        )
    )
    roi = result.scalar_one_or_none()
    if not roi:
        raise HTTPException(status_code=404, detail="Impact link not found")
    await session.delete(roi)
    return {"deleted": True}


@router.get("/objectives/{objective_id}/routine-impacts")
async def get_objective_routine_impacts(
    objective_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """List all routines that impact an objective, with scores."""
    rows = await session.execute(
        select(RoutineObjectiveImpact, Routine.title, Routine.status, Routine.time_of_day)
        .join(Routine, Routine.id == RoutineObjectiveImpact.routine_id)
        .where(
            RoutineObjectiveImpact.user_id == user.id,
            RoutineObjectiveImpact.objective_id == objective_id,
        )
        .order_by(RoutineObjectiveImpact.impact_score.desc())
    )
    return {
        "objective_id": objective_id,
        "routine_impacts": [
            {
                "routine_id": roi.routine_id,
                "routine_title": r_title,
                "routine_status": r_status,
                "routine_time_of_day": r_tod,
                "impact_score": roi.impact_score,
                "notes": roi.notes,
            }
            for roi, r_title, r_status, r_tod in rows
        ],
    }

@router.delete("/settings/account")
async def delete_account(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Delete user account and all associated data."""
    await session.delete(user)
    await session.flush()
    return {"ok": True}


# ─── Achievements ──────────────────────────────────────────────────────────────

@router.get("/achievements")
async def list_achievements(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Get all achievements with unlock status and progress hints."""
    # Load all achievements
    all_result = await session.execute(select(Achievement).order_by(Achievement.category, Achievement.xp_reward))
    all_achievements = all_result.scalars().all()

    # Load user's unlocked achievements
    unlocked_result = await session.execute(
        select(UserAchievement).where(UserAchievement.user_id == user.id)
    )
    unlocked_map: dict[int, "UserAchievement"] = {
        ua.achievement_id: ua for ua in unlocked_result.scalars().all()
    }

    # Gather progress data for count-based achievements
    done_tasks_result = await session.execute(
        select(func.count()).select_from(Task).where(and_(Task.user_id == user.id, Task.status == "done"))
    )
    done_tasks = done_tasks_result.scalar() or 0

    objectives_result = await session.execute(
        select(func.count()).select_from(Objective).where(Objective.user_id == user.id)
    )
    total_objectives = objectives_result.scalar() or 0

    reflections_result = await session.execute(
        select(func.count()).select_from(WeeklyReflection).where(
            and_(WeeklyReflection.user_id == user.id, WeeklyReflection.status.in_(["in_progress", "completed"]))
        )
    )
    total_reflections = reflections_result.scalar() or 0

    brain_dumps_result = await session.execute(
        select(func.count()).select_from(BrainDump).where(BrainDump.user_id == user.id)
    )
    total_brain_dumps = brain_dumps_result.scalar() or 0

    workouts_result = await session.execute(
        select(func.count()).select_from(Log).where(and_(Log.user_id == user.id, Log.log_type == "workout"))
    )
    total_workouts = workouts_result.scalar() or 0

    water_result = await session.execute(
        select(Log).where(and_(Log.user_id == user.id, Log.log_type == "water"))
    )
    total_water = sum((l.data or {}).get("amount", 0) for l in water_result.scalars().all())

    # Calculate streak
    since_60 = datetime.combine(date.today() - timedelta(days=60), datetime.min.time())
    log_dates_result = await session.execute(
        select(Log.logged_at).where(and_(Log.user_id == user.id, Log.logged_at >= since_60))
    )
    active_dates = {dt.date() for dt in log_dates_result.scalars().all()}
    streak = 0
    check_date = date.today()
    while check_date in active_dates:
        streak += 1
        check_date -= timedelta(days=1)

    def get_progress(achievement: Achievement) -> dict:
        key = achievement.key
        condition_type = achievement.condition_type
        condition_value = achievement.condition_value

        if condition_type == "streak":
            return {"current": streak, "target": condition_value}
        if condition_type == "count":
            if key in ("macher", "hundertschaft"):
                return {"current": done_tasks, "target": condition_value}
            if key == "zielstrebig":
                return {"current": total_objectives, "target": condition_value}
            if key == "selbstreflektiert":
                return {"current": total_reflections, "target": condition_value}
            if key == "hydration_hero":
                return {"current": int(total_water), "target": condition_value}
            if key == "brain_dumper":
                return {"current": total_brain_dumps, "target": condition_value}
            if key == "gym_rat":
                return {"current": total_workouts, "target": condition_value}
        return {"current": None, "target": None}

    return {
        "achievements": [
            {
                "id": a.id,
                "key": a.key,
                "title": a.title,
                "description": a.description,
                "emoji": a.emoji,
                "category": a.category,
                "xp_reward": a.xp_reward,
                "condition_type": a.condition_type,
                "condition_value": a.condition_value,
                "unlocked": a.id in unlocked_map,
                "unlocked_at": unlocked_map[a.id].unlocked_at.isoformat() if a.id in unlocked_map else None,
                "progress": get_progress(a),
            }
            for a in all_achievements
        ]
    }


@router.get("/achievements/recent")
async def recent_achievements(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    limit: int = Query(5, ge=1, le=20),
) -> dict:
    """Get the most recently unlocked achievements for the user."""
    result = await session.execute(
        select(UserAchievement)
        .options(selectinload(UserAchievement.achievement))
        .where(UserAchievement.user_id == user.id)
        .order_by(UserAchievement.unlocked_at.desc())
        .limit(limit)
    )
    user_achievements = result.scalars().all()
    return {
        "recent": [
            {
                "id": ua.achievement.id,
                "key": ua.achievement.key,
                "title": ua.achievement.title,
                "description": ua.achievement.description,
                "emoji": ua.achievement.emoji,
                "category": ua.achievement.category,
                "xp_reward": ua.achievement.xp_reward,
                "unlocked_at": ua.unlocked_at.isoformat(),
            }
            for ua in user_achievements
        ]
    }


@router.post("/achievements/check")
async def trigger_achievement_check(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Manually trigger achievement checking + unlock for the current user.

    Useful to call after bulk operations or when syncing from Telegram.
    Returns list of newly unlocked achievements.
    """
    from bot.core.achievements import check_achievements

    newly_unlocked = await check_achievements(session, user.id)
    return {
        "ok": True,
        "newly_unlocked": [
            {"key": a.key, "title": a.title, "emoji": a.emoji, "xp_reward": a.xp_reward}
            for a in newly_unlocked
        ],
        "count": len(newly_unlocked),
    }


# ─── Reflections Endpoints ─────────────────────────────────────────────────────

def _reflection_dict(r: WeeklyReflection) -> dict:
    return {
        "id": r.id,
        "week_start": r.week_start.isoformat(),
        "week_number": r.week_number,
        "year": r.year,
        "status": r.status,
        "week_score": r.week_score,
        "biggest_win": r.biggest_win,
        "biggest_blocker": r.biggest_blocker,
        "key_learning": r.key_learning,
        "raw_answers": r.raw_answers or {},
        "priorities_next_week": r.priorities_next_week,
        "top_priorities": (r.raw_answers or {}).get("top_priorities", []),
        "ai_summary": r.ai_summary,
        "created_at": r.created_at.isoformat(),
        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
    }


@router.get("/reflections")
async def list_reflections(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Get all weekly reflections for the user, ordered by most recent."""
    result = await session.execute(
        select(WeeklyReflection)
        .where(WeeklyReflection.user_id == user.id)
        .order_by(WeeklyReflection.week_start.desc())
    )
    reflections = result.scalars().all()
    return {"reflections": [_reflection_dict(r) for r in reflections]}


@router.get("/reflections/{reflection_id}")
async def get_reflection(
    reflection_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Get a single reflection by ID."""
    result = await session.execute(
        select(WeeklyReflection).where(and_(
            WeeklyReflection.id == reflection_id,
            WeeklyReflection.user_id == user.id,
        ))
    )
    r = result.scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="Reflection not found")
    return _reflection_dict(r)


@router.post("/reflections/{reflection_id}/insights")
async def regenerate_reflection_insights(
    reflection_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Regenerate AI insights for a completed reflection using GPT-4o."""
    from bot.core.weekly_reflections import _generate_ai_summary

    result = await session.execute(
        select(WeeklyReflection).where(and_(
            WeeklyReflection.id == reflection_id,
            WeeklyReflection.user_id == user.id,
        ))
    )
    r = result.scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="Reflection not found")
    if r.status != "completed":
        raise HTTPException(status_code=400, detail="Reflection not yet completed")

    try:
        ai_summary = await _generate_ai_summary(session, r)
        r.ai_summary = ai_summary
        await session.flush()
        return {"ok": True, "ai_summary": ai_summary}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI generation failed: {str(e)}")


@router.delete("/reflections/{reflection_id}")
async def delete_reflection(
    reflection_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Delete a weekly reflection."""
    result = await session.execute(
        select(WeeklyReflection).where(and_(
            WeeklyReflection.id == reflection_id,
            WeeklyReflection.user_id == user.id,
        ))
    )
    r = result.scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="Reflection not found")
    await session.delete(r)
    await session.flush()
    return {"ok": True, "deleted_id": reflection_id}


class ReflectionPatchBody(BaseModel):
    top_priorities: Optional[list] = None


@router.patch("/reflections/{reflection_id}")
async def patch_reflection(
    reflection_id: int,
    body: ReflectionPatchBody,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Update reflection fields (e.g. top_priorities for the week)."""
    result = await session.execute(
        select(WeeklyReflection).where(and_(
            WeeklyReflection.id == reflection_id,
            WeeklyReflection.user_id == user.id,
        ))
    )
    r = result.scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="Reflection not found")
    if body.top_priorities is not None:
        raw = dict(r.raw_answers or {})
        raw["top_priorities"] = [str(p) for p in body.top_priorities[:3]]
        r.raw_answers = raw
    await session.flush()
    return _reflection_dict(r)


# ─── Daily Suggestions Endpoint ────────────────────────────────────────────────

@router.get("/suggestions/today")
async def get_todays_suggestions(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Return today's AI suggestions, generating them on-demand if not yet available."""
    import logging as _logging
    from zoneinfo import ZoneInfo
    today = datetime.now(tz=ZoneInfo("Europe/Berlin")).date()
    try:
        suggestions = await get_or_generate_suggestions(session, user, today)
    except Exception:
        _logging.getLogger(__name__).exception("Failed to get/generate suggestions for user %s", user.id)
        suggestions = None
    if suggestions is None:
        return {"date": today.isoformat(), "suggestions": None}
    return {"date": today.isoformat(), "suggestions": suggestions}


@router.get("/suggestions/history")
async def get_suggestions_history(
    days: int = Query(14, ge=1, le=90),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Return the last N days of daily suggestions for the user."""
    from datetime import date as _date, timedelta as _timedelta
    cutoff = _date.today() - _timedelta(days=days)
    result = await session.execute(
        select(DailySuggestion)
        .where(and_(DailySuggestion.user_id == user.id, DailySuggestion.date >= cutoff))
        .order_by(DailySuggestion.date.desc())
    )
    rows = result.scalars().all()
    return {
        "history": [
            {"date": r.date.isoformat(), "suggestions": r.suggestions, "created_at": r.created_at.isoformat()}
            for r in rows
        ]
    }


@router.post("/suggestions/regenerate")
async def regenerate_todays_suggestions(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Delete today's cached suggestions and regenerate them via GPT-4o."""
    from zoneinfo import ZoneInfo
    from datetime import date as _date
    today = _date.today()
    # Delete existing record so get_or_generate_suggestions creates a fresh one
    existing = await session.execute(
        select(DailySuggestion).where(and_(
            DailySuggestion.user_id == user.id,
            DailySuggestion.date == today,
        ))
    )
    row = existing.scalar_one_or_none()
    if row:
        await session.delete(row)
        await session.flush()
    try:
        new_suggestions = await get_or_generate_suggestions(session, user, today)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI generation failed: {str(e)}")
    return {"date": today.isoformat(), "suggestions": new_suggestions}


# ─── E3: Behavioral Pattern Detector ──────────────────────────────────────────

@router.get("/autopilot/patterns")
async def get_behavioral_patterns(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Detect behavioral patterns: missed routines, context drift, mood trends."""
    today = date.today()
    thirty_ago = datetime.combine(today - timedelta(days=30), datetime.min.time())
    fourteen_ago = datetime.combine(today - timedelta(days=14), datetime.min.time())
    seven_ago = datetime.combine(today - timedelta(days=7), datetime.min.time())

    # ── 1. Missed routines ───────────────────────────────────────────────────
    routines_res = await session.execute(
        select(Routine).where(Routine.user_id == user.id)
    )
    routines = routines_res.scalars().all()

    missed_routines = []
    for routine in routines:
        count_res = await session.execute(
            select(func.count()).select_from(RoutineCompletion).where(and_(
                RoutineCompletion.routine_id == routine.id,
                RoutineCompletion.completed_at >= thirty_ago,
            ))
        )
        completions = count_res.scalar() or 0
        rate = min(round((completions / 30) * 100), 100)
        if rate < 50:
            missed_routines.append({
                "id": routine.id,
                "title": routine.title,
                "completion_rate": rate,
                "completions_30d": completions,
            })
    missed_routines.sort(key=lambda x: x["completion_rate"])

    # ── 2. Context drift: active objectives with no recent task done ─────────
    obj_res = await session.execute(
        select(Objective).where(and_(
            Objective.user_id == user.id,
            Objective.status == "active",
        ))
    )
    objectives = obj_res.scalars().all()

    drifting = []
    for obj in objectives:
        done_res = await session.execute(
            select(func.count()).select_from(Task).where(and_(
                Task.objective_id == obj.id,
                Task.status == "done",
                Task.updated_at >= fourteen_ago,
            ))
        )
        recent_done = done_res.scalar() or 0
        if recent_done == 0:
            drifting.append({
                "id": obj.id,
                "title": obj.title,
                "category": obj.category,
                "days_inactive": 14,
            })

    # ── 3. Mood trend: recent 7d vs prior 7d ────────────────────────────────
    mood_logs_res = await session.execute(
        select(Log).where(and_(
            Log.user_id == user.id,
            Log.log_type == "mood",
            Log.logged_at >= datetime.combine(today - timedelta(days=14), datetime.min.time()),
        ))
    )
    mood_logs = mood_logs_res.scalars().all()

    recent_moods = [
        l.data.get("mood") for l in mood_logs
        if l.logged_at >= seven_ago and l.data.get("mood") is not None
    ]
    prior_moods = [
        l.data.get("mood") for l in mood_logs
        if l.logged_at < seven_ago and l.data.get("mood") is not None
    ]

    mood_trend = None
    if recent_moods and prior_moods:
        recent_avg = round(sum(recent_moods) / len(recent_moods), 1)
        prior_avg = round(sum(prior_moods) / len(prior_moods), 1)
        delta = recent_avg - prior_avg
        mood_trend = {
            "recent_avg": recent_avg,
            "prior_avg": prior_avg,
            "delta": round(delta, 1),
            "direction": "up" if delta > 0.4 else "down" if delta < -0.4 else "stable",
        }

    return {
        "missed_routines": missed_routines[:5],
        "drifting_objectives": drifting[:5],
        "mood_trend": mood_trend,
    }


@router.get("/autopilot/pattern-insights")
async def get_pattern_insights(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Get stored pattern insights + consistency score for this user."""
    from bot.core.pattern_engine import _compute_consistency_score
    from bot.core.insights import get_active_insights

    insights = await get_active_insights(session, user.id)
    consistency = await _compute_consistency_score(session, user.id, date.today())

    return {
        "insights": [
            {
                "id": ins.id,
                "type": ins.insight_type,
                "title": ins.title,
                "description": ins.description,
                "created_at": ins.created_at.isoformat(),
            }
            for ins in insights
        ],
        "consistency_score": consistency,
    }


@router.post("/autopilot/pattern-insights/refresh")
async def refresh_pattern_insights(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Trigger a fresh pattern analysis run on demand."""
    from bot.core.pattern_engine import run_pattern_analysis
    result = await run_pattern_analysis(session, user.id)
    await session.commit()
    return {
        "ok": True,
        "insights_generated": len(result.get("insights", [])),
        "consistency_score": result.get("consistency_score"),
    }


# ─── E4: Adaptive Suggestion Timing ───────────────────────────────────────────

@router.get("/autopilot/active-hours")
async def get_active_hours(
    days: int = Query(30, ge=7, le=90),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Analyse log timestamps to detect when the user is most active.

    Returns hour buckets (0–23) with activity counts,
    peak hour, and recommended nudge windows.
    """
    cutoff = datetime.combine(date.today() - timedelta(days=days), datetime.min.time())
    logs_res = await session.execute(
        select(Log.logged_at).where(and_(
            Log.user_id == user.id,
            Log.logged_at >= cutoff,
        ))
    )
    timestamps = [row[0] for row in logs_res.all()]

    # Count activity per hour (0–23)
    hour_counts: dict[int, int] = {h: 0 for h in range(24)}
    for ts in timestamps:
        hour_counts[ts.hour] += 1

    total = sum(hour_counts.values())
    if total == 0:
        return {"hours": hour_counts, "peak_hour": None, "recommended_windows": [], "total_events": 0}

    peak_hour = max(hour_counts, key=lambda h: hour_counts[h])

    # Identify top-3 windows (groups of 2 hours with highest combined activity)
    window_scores = {}
    for h in range(24):
        window_scores[h] = hour_counts[h] + hour_counts[(h + 1) % 24]
    sorted_windows = sorted(window_scores, key=lambda h: window_scores[h], reverse=True)
    recommended_windows = [
        {"start_hour": h, "end_hour": (h + 2) % 24, "activity_score": window_scores[h]}
        for h in sorted_windows[:3]
        if window_scores[h] > 0
    ]

    return {
        "hours": hour_counts,
        "peak_hour": peak_hour,
        "recommended_windows": recommended_windows,
        "total_events": total,
        "days_analyzed": days,
    }


# ─── E5: Autopilot Confidence Scoring ─────────────────────────────────────────

@router.get("/autopilot/confidence")
async def get_autopilot_confidence(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Calculate autopilot confidence score (0–100) + escalation flags.

    Confidence is derived from:
    - Data recency: how recently the user logged data
    - Objective coverage: % of active objectives with recent tasks
    - Routine adherence: avg completion rate across all routines
    - Reflection freshness: days since last completed reflection

    Escalation rules fire when confidence < 40 or specific signals missing.
    """
    today = date.today()
    seven_ago = datetime.combine(today - timedelta(days=7), datetime.min.time())
    fourteen_ago = datetime.combine(today - timedelta(days=14), datetime.min.time())
    thirty_ago = datetime.combine(today - timedelta(days=30), datetime.min.time())

    scores: dict[str, int] = {}
    escalations: list[dict] = []

    # ── Data recency (0–25 pts) ────────────────────────────────────────────
    recent_log_res = await session.execute(
        select(func.count()).select_from(Log).where(and_(
            Log.user_id == user.id,
            Log.logged_at >= seven_ago,
        ))
    )
    recent_logs = recent_log_res.scalar() or 0
    data_score = min(25, int((recent_logs / 10) * 25))
    scores["data_recency"] = data_score
    if recent_logs == 0:
        escalations.append({"code": "no_recent_data", "severity": "high",
                            "message": "Keine Aktivität in den letzten 7 Tagen"})

    # ── Objective coverage (0–25 pts) ──────────────────────────────────────
    obj_res = await session.execute(
        select(Objective).where(and_(
            Objective.user_id == user.id,
            Objective.status == "active",
        ))
    )
    objectives = obj_res.scalars().all()
    covered = 0
    for obj in objectives:
        task_res = await session.execute(
            select(func.count()).select_from(Task).where(and_(
                Task.objective_id == obj.id,
                Task.status == "done",
                Task.updated_at >= fourteen_ago,
            ))
        )
        if (task_res.scalar() or 0) > 0:
            covered += 1
    coverage_pct = (covered / len(objectives)) if objectives else 1.0
    coverage_score = int(coverage_pct * 25)
    scores["objective_coverage"] = coverage_score
    if objectives and coverage_pct < 0.5:
        escalations.append({"code": "low_objective_coverage", "severity": "medium",
                            "message": f"Nur {covered}/{len(objectives)} Ziele aktiv (letzte 14 Tage)"})

    # ── Routine adherence (0–25 pts) ───────────────────────────────────────
    routine_res = await session.execute(
        select(Routine).where(Routine.user_id == user.id)
    )
    routines = routine_res.scalars().all()
    if routines:
        rates = []
        for r in routines:
            count_res = await session.execute(
                select(func.count()).select_from(RoutineCompletion).where(and_(
                    RoutineCompletion.routine_id == r.id,
                    RoutineCompletion.completed_at >= thirty_ago,
                ))
            )
            rate = min((count_res.scalar() or 0) / 30, 1.0)
            rates.append(rate)
        avg_rate = sum(rates) / len(rates)
        routine_score = int(avg_rate * 25)
    else:
        avg_rate = 0.0
        routine_score = 0
    scores["routine_adherence"] = routine_score
    if routines and avg_rate < 0.3:
        escalations.append({"code": "low_routine_adherence", "severity": "medium",
                            "message": f"Routinen-Erfüllungsrate unter 30% ({round(avg_rate*100)}%)"})

    # ── Reflection freshness (0–25 pts) ────────────────────────────────────
    latest_reflection_res = await session.execute(
        select(WeeklyReflection)
        .where(and_(
            WeeklyReflection.user_id == user.id,
            WeeklyReflection.status == "completed",
        ))
        .order_by(WeeklyReflection.week_start.desc())
        .limit(1)
    )
    latest_reflection = latest_reflection_res.scalar_one_or_none()
    if latest_reflection:
        days_since = (today - latest_reflection.week_start).days
        reflection_score = max(0, 25 - int((days_since / 14) * 25))
        if days_since > 21:
            escalations.append({"code": "stale_reflection", "severity": "low",
                                "message": f"Letzte Reflexion vor {days_since} Tagen"})
    else:
        reflection_score = 0
        escalations.append({"code": "no_reflection", "severity": "low",
                            "message": "Noch keine wöchentliche Reflexion"})
    scores["reflection_freshness"] = reflection_score

    total = sum(scores.values())
    level = "high" if total >= 70 else "medium" if total >= 40 else "low"

    return {
        "confidence": total,
        "level": level,
        "scores": scores,
        "escalations": escalations,
    }


# ─── Autopilot Notification Endpoints (A1) ─────────────────────────────────────

def _notification_dict(n: AutopilotNotification) -> dict:
    return {
        "id": n.id,
        "notification_type": n.notification_type,
        "title": n.title,
        "body": n.body,
        "status": n.status,
        "snoozed_until": n.snoozed_until.isoformat() if n.snoozed_until else None,
        "source": n.source,
        "linked_task_id": n.linked_task_id,
        "created_at": n.created_at.isoformat(),
    }


@router.get("/notifications")
async def list_notifications(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    status: Optional[str] = Query(None, description="Filter by status: pending, acknowledged, snoozed"),
    limit: int = Query(20, ge=1, le=100),
) -> dict:
    """List autopilot notifications for the current user.

    Returns pending nudges by default (status=pending).
    Pass status=all to get every notification.
    """
    from datetime import timezone as _tz
    now = datetime.now(tz=_tz.utc).replace(tzinfo=None)

    filter_status = status or "pending"
    if filter_status == "all":
        where_clause = AutopilotNotification.user_id == user.id
    else:
        where_clause = and_(
            AutopilotNotification.user_id == user.id,
            AutopilotNotification.status == filter_status,
        )

    result = await session.execute(
        select(AutopilotNotification)
        .where(where_clause)
        .order_by(AutopilotNotification.created_at.desc())
        .limit(limit)
    )
    notifications = result.scalars().all()

    # Auto-expire snoozed notifications whose snooze window has passed
    for n in notifications:
        if n.status == "snoozed" and n.snoozed_until and n.snoozed_until <= now:
            n.status = "pending"
    await session.flush()

    pending = [n for n in notifications if n.status == "pending"]
    return {
        "notifications": [_notification_dict(n) for n in notifications],
        "pending_count": len(pending),
        "latest": _notification_dict(pending[0]) if pending else None,
    }


# ─── Epic 2.1: Unified Planner Snapshot models ────────────────────────────────

class PlannerBlockerRef(BaseModel):
    type: str
    id: int
    title: Optional[str] = None


class PlannerBlocker(BaseModel):
    task_id: int
    task_title: str
    blocked_by: list[PlannerBlockerRef]


class PlannerProgressSummary(BaseModel):
    completed_today: int
    open_tasks: int
    active_objectives: int
    routines_done: int
    routines_pending: int
    pending_reminders: int
    pending_nudges: int


class SnoozeRequest(BaseModel):
    minutes: int = 60  # default snooze 60 minutes


@router.get("/notifications/counts")
async def notification_counts(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Lightweight endpoint returning pending/snoozed/total notification counts."""
    from datetime import timezone as _tz
    now = datetime.now(tz=_tz.utc).replace(tzinfo=None)

    result = await session.execute(
        select(AutopilotNotification).where(
            AutopilotNotification.user_id == user.id,
        )
    )
    all_notifs = result.scalars().all()

    # Auto-expire snoozed items whose window has passed
    for n in all_notifs:
        if n.status == "snoozed" and n.snoozed_until and n.snoozed_until <= now:
            n.status = "pending"
    await session.flush()

    pending = sum(1 for n in all_notifs if n.status == "pending")
    snoozed = sum(1 for n in all_notifs if n.status == "snoozed")
    return {"pending": pending, "snoozed": snoozed, "total": len(all_notifs)}


@router.post("/notifications/{notification_id}/acknowledge")
async def acknowledge_notification(
    notification_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Mark a notification as acknowledged (dismissed)."""
    result = await session.execute(
        select(AutopilotNotification).where(
            and_(
                AutopilotNotification.id == notification_id,
                AutopilotNotification.user_id == user.id,
            )
        )
    )
    notification = result.scalar_one_or_none()
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    notification.status = "acknowledged"
    await session.flush()
    return {"ok": True, "notification": _notification_dict(notification)}


# ─── Daily Plan Orchestrator (A2) ──────────────────────────────────────────────

def _build_deterministic_daily_plan(
    tasks: list,
    routines: list,
    completed_routine_ids: set,
    events: list,
    today: date,
    top_priorities: Optional[list] = None,
    now_dt: Optional[datetime] = None,
    graph_data: Optional[dict] = None,
) -> dict:
    """Build a fully deterministic plan — no AI required.

    Epic 2.2: suggested_blocks now use the calendar-aware free-slot planner.
    New optional kwargs (now_dt, graph_data) are backward compatible — callers
    that omit them get deterministic fallback behaviour identical to before.
    """
    from bot.core.free_slot_planner import plan_free_slots as _plan_slots

    # Score tasks
    scored: list[tuple[int, object]] = []
    for t in tasks:
        score = (6 - t.priority) * 10
        if t.due_date:
            if t.due_date < today:
                score += 40
            elif t.due_date == today:
                score += 30
            elif t.due_date <= today + timedelta(days=2):
                score += 20
            elif t.due_date <= today + timedelta(days=7):
                score += 10
        # Boost tasks in categories matching this week's top priorities (P2.1)
        if top_priorities and t.category and t.category in top_priorities:
            score = int(score * 1.5)
        scored.append((score, t))
    scored.sort(key=lambda x: -x[0])

    # Sections
    sections: list[dict] = []

    # 1. Top tasks
    task_items = []
    for sc, t in scored[:5]:
        reason = _get_task_reason(t)
        boosted = bool(top_priorities and t.category and t.category in top_priorities)
        task_items.append({
            "id": t.id,
            "type": "task",
            "title": t.title,
            "reason": reason,
            "category": t.category,
            "priority": t.priority,
            "is_overdue": bool(t.due_date and t.due_date < today),
            "boosted": boosted,
        })
    if task_items:
        sections.append({"id": "top_tasks", "title": "Top Priorities", "items": task_items})

    # 2. Routines
    routine_items = []
    for r in routines:
        done = r.id in completed_routine_ids
        routine_items.append({
            "id": r.id,
            "type": "routine",
            "title": r.title,
            "reason": "Completed" if done else "Pending",
            "completed": done,
            "time_of_day": r.time_of_day,
        })
    if routine_items:
        sections.append({"id": "routines", "title": "Routines Today", "items": routine_items})

    # 3. Today's calendar events
    event_items = []
    for e in events:
        event_items.append({
            "id": e.id,
            "type": "event",
            "title": e.title,
            "reason": e.start_time.strftime("%H:%M") if not e.all_day else "All day",
            "start_time": _localize_berlin(e.start_time),
            "end_time": _localize_berlin(e.end_time) if e.end_time else None,
            "all_day": e.all_day,
        })
    if event_items:
        sections.append({"id": "events", "title": "Events Today", "items": event_items})

    # ── Epic 2.2: Calendar-aware free-slot suggested blocks ───────────────────
    # Use the free-slot planner; enrich block dicts with legacy "title"/"reason"
    # fields so existing consumers continue to work unchanged.
    slot_plan = _plan_slots(
        events=events,
        tasks=[t for _, t in scored],
        today=today,
        now_dt=now_dt,
        graph_data=graph_data,
    )
    suggested_blocks: list[dict] = []
    for blk in slot_plan["suggested_blocks"]:
        enriched = dict(blk)
        # Backward-compat aliases: "title" and "reason" expected by older consumers
        enriched.setdefault("title", blk.get("task_title") or "")
        enriched.setdefault("reason", blk.get("task_reason") or blk.get("slot_reason") or "")
        suggested_blocks.append(enriched)

    # Summary sentence
    open_count = len(scored)
    overdue_count = sum(1 for sc, t in scored if t.due_date and t.due_date < today)
    pending_routines = sum(1 for r in routines if r.id not in completed_routine_ids)
    parts: list[str] = []
    if open_count:
        parts.append(f"{open_count} open task{'s' if open_count != 1 else ''}")
    if overdue_count:
        parts.append(f"{overdue_count} overdue")
    if pending_routines:
        parts.append(f"{pending_routines} routine{'s' if pending_routines != 1 else ''} pending")
    if event_items:
        parts.append(f"{len(event_items)} event{'s' if len(event_items) != 1 else ''} today")
    summary = " · ".join(parts) if parts else "Nothing scheduled — enjoy the free time!"

    return {
        "summary": summary,
        "sections": sections,
        "suggested_blocks": suggested_blocks,
        # Epic 2.2: expose planner metadata for dashboard/mobile consumers
        "free_slot_meta": {
            "free_minutes_total": slot_plan["free_minutes_total"],
            "free_minutes_used": slot_plan["free_minutes_used"],
            "windows": slot_plan["windows"],
            "fallback": slot_plan["fallback"],
            "data_quality": slot_plan["data_quality"],
        },
    }


# ─── P2.2: Explainability helpers ─────────────────────────────────────────────

def _compute_next_action_reason(task_dict: dict, today: date) -> str:
    """Compute a human-readable reason for why a task is the next action."""
    due_str = task_dict.get("due_date")
    due = date.fromisoformat(due_str) if due_str else None
    if due and due < today:
        return "Überfällig"
    if due and due == today:
        return "Heute fällig"
    if task_dict.get("priority") == 1:
        return "Höchste Priorität"
    obj_id = task_dict.get("objective_id")
    if obj_id:
        # Caller may populate objective_title; use it if available
        obj_title = task_dict.get("objective_title")
        if obj_title:
            return f"Ziel: {obj_title}"
    return "Nächste offene Aufgabe"


@router.get("/autopilot/next-action")
async def get_next_action_endpoint(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Return next unblocked task with explainability metadata (Epic 1.2).

    Response fields (backward compatible — only additions):
    - task: full task dict including why_selected, blocked_by, unlocks_count, contributes_to
    - reason: human-readable selection reason (P2.2, kept for compat)
    - score: null (reserved)
    - why_selected: same as task.why_selected, surfaced at top level for convenience
    - blocked_by: list of blocking node refs (empty for the selected task)
    - unlocks_count: how many tasks this selection unlocks
    - contributes_to: list of objective/KR nodes this task contributes to
    """
    from bot.core.completion_hooks import get_next_unblocked_action as _get_next

    today = date.today()
    t = await _get_next(session, user.id)
    if not t:
        return {
            "task": None,
            "reason": None,
            "score": None,
            "why_selected": None,
            "blocked_by": [],
            "unlocks_count": 0,
            "contributes_to": [],
            # Epic 4.2 trust signals
            "source_type": "deterministic_fallback",
            "confidence_level": "low",
            "confidence_reason": "Keine offene unblocked Aufgabe gefunden",
        }

    # Enrich with objective title if needed
    obj_id = t.get("objective_id")
    if obj_id and not t.get("objective_title"):
        obj_row = await session.get(Objective, obj_id)
        if obj_row:
            t = {**t, "objective_title": obj_row.title}

    reason = _compute_next_action_reason(t, today)
    confidence_reason = "Regelbasiert aus unblocked Task-Graph" if t.get("why_selected") else "Regelbasiert nach Priorität/Fälligkeit"
    return {
        "task": t,
        "reason": reason,
        "score": None,
        # Epic 1.2: top-level explainability fields
        "why_selected": t.get("why_selected"),
        "blocked_by": t.get("blocked_by", []),
        "unlocks_count": t.get("unlocks_count", 0),
        "contributes_to": t.get("contributes_to", []),
        # Epic 4.2 trust signals (additive)
        "source_type": "deterministic_fallback",
        "confidence_level": "high",
        "confidence_reason": confidence_reason,
    }


@router.get("/autopilot/today")
async def get_autopilot_today(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Unified autopilot snapshot for today.

    Contract-first: see SPEC_AUTOPILOT_API.md.

    Composes:
    - next_action (CORE-7)
    - daily plan (CORE-6, via deterministic builder)
    - pending reminders count
    - pending nudges count
    - progress summary
    """
    from datetime import timezone as _tz

    from bot.core.completion_hooks import get_next_unblocked_action

    today = date.today()

    # Plan: reuse deterministic daily plan builder (and optionally AI summary below)
    plan = await get_daily_plan(user=user, session=session)

    # Next action
    next_action_task = await get_next_unblocked_action(session, user.id)
    next_action = None
    if next_action_task:
        next_action = {
            "type": "task",
            "reason": _compute_next_action_reason(next_action_task, today),
            **next_action_task,
        }

    # Counts
    now = datetime.now(tz=_tz.utc).replace(tzinfo=None)
    rem_count_res = await session.execute(
        select(func.count(ScheduledReminder.id)).where(
            and_(
                ScheduledReminder.user_id == user.id,
                ScheduledReminder.status == "pending",
                ScheduledReminder.scheduled_for >= now,
            )
        )
    )
    pending_reminders = int(rem_count_res.scalar() or 0)

    nudge_count_res = await session.execute(
        select(func.count(AutopilotNotification.id)).where(
            and_(
                AutopilotNotification.user_id == user.id,
                AutopilotNotification.status == "pending",
            )
        )
    )
    pending_nudges = int(nudge_count_res.scalar() or 0)

    # Progress summary
    obj_count_res = await session.execute(
        select(func.count(Objective.id)).where(
            and_(Objective.user_id == user.id, Objective.status == "active")
        )
    )
    active_objectives = int(obj_count_res.scalar() or 0)

    completed_today_res = await session.execute(
        select(func.count(Task.id)).where(
            and_(
                Task.user_id == user.id,
                Task.completed_at.is_not(None),
                Task.completed_at >= datetime.combine(today, datetime.min.time()),
            )
        )
    )
    completed_today = int(completed_today_res.scalar() or 0)

    # Open tasks count
    open_tasks_res = await session.execute(
        select(func.count(Task.id)).where(
            and_(
                Task.user_id == user.id,
                Task.status.in_(["todo", "in_progress"]),
            )
        )
    )
    open_tasks = int(open_tasks_res.scalar() or 0)

    # Action queue: top 5 active items + total_active count
    active_queue_res = await session.execute(
        select(ActionQueueItem)
        .where(
            and_(
                ActionQueueItem.user_id == user.id,
                ActionQueueItem.state != "completed",
            )
        )
        .order_by(ActionQueueItem.created_at.desc())
        .limit(5)
    )
    active_queue_items = list(active_queue_res.scalars().all())

    total_active_res = await session.execute(
        select(func.count(ActionQueueItem.id)).where(
            and_(
                ActionQueueItem.user_id == user.id,
                ActionQueueItem.state.in_(["planned", "suggested", "accepted"]),
            )
        )
    )
    total_active_queue = int(total_active_res.scalar() or 0)

    # Notification counts (pending / snoozed / total)
    all_notifs_res = await session.execute(
        select(AutopilotNotification).where(
            AutopilotNotification.user_id == user.id,
        )
    )
    all_notifs = all_notifs_res.scalars().all()
    # Auto-expire snoozed items whose window has passed
    for n in all_notifs:
        if n.status == "snoozed" and n.snoozed_until and n.snoozed_until <= now:
            n.status = "pending"
    notif_pending = sum(1 for n in all_notifs if n.status == "pending")
    notif_snoozed = sum(1 for n in all_notifs if n.status == "snoozed")

    return {
        "date": today.isoformat(),
        "next_action": next_action,
        "plan": plan,
        "counts": {
            "pending_nudges": pending_nudges,
            "pending_reminders": pending_reminders,
        },
        "progress": {
            "active_objectives": active_objectives,
            "completed_today": completed_today,
        },
        "open_tasks": open_tasks,
        "action_queue": {
            "items": [_queue_item_dict(i) for i in active_queue_items],
            "total_active": total_active_queue,
        },
        "notification_counts": {
            "pending": notif_pending,
            "snoozed": notif_snoozed,
            "total": len(all_notifs),
        },
    }


@router.get("/autopilot/snapshot")
async def get_autopilot_snapshot(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Epic 2.1 — Unified planner snapshot contract.

    Single stable endpoint composing all planner signals:
    - next_action: graph-aware unblocked next task (Epic 1.2)
    - today_plan: tasks + routines + calendar sections (deterministic + optional AI summary)
    - blockers: open tasks currently blocked by other open tasks
    - suggestions: top pending suggestion notifications (read-only, no side-effects)
    - progress_summary: day completion stats

    Preserves all existing /autopilot/* endpoints — this is additive only.
    """
    import asyncio as _asyncio
    import logging as _log
    from datetime import timezone as _tz
    from bot.core.completion_hooks import get_next_unblocked_action as _get_next
    from bot.core.calendar import get_todays_events as _get_events
    from bot.core.routines import get_todays_completions as _get_completions

    _logger = _log.getLogger(__name__)
    today = date.today()
    now = datetime.now(tz=_tz.utc).replace(tzinfo=None)

    # ── 1. Parallel data fetch ──────────────────────────────────────────────────
    (
        next_action_task,
        tasks_result,
        routines_result,
        completed_ids,
        events,
    ) = await _asyncio.gather(
        _get_next(session, user.id),
        session.execute(
            select(Task)
            .options(
                selectinload(Task.key_result).selectinload(KeyResult.objective),
                selectinload(Task.objective),
            )
            .where(and_(
                Task.user_id == user.id,
                Task.status.in_(["todo", "in_progress"]),
                Task.category != "shopping",
            ))
            .order_by(Task.priority.asc(), Task.due_date.asc().nulls_last())
        ),
        session.execute(
            select(Routine)
            .where(and_(Routine.user_id == user.id, Routine.status == "active"))
            .order_by(Routine.sort_order, Routine.id)
        ),
        _get_completions(session, user.id),
        _get_events(session, user.id),
    )

    tasks = list(tasks_result.scalars().all())
    routines = list(routines_result.scalars().all())
    completed_routine_ids_set: set[int] = set(completed_ids) if completed_ids else set()
    task_by_id = {t.id: t for t in tasks}
    task_ids = list(task_by_id.keys())

    # ── 2. today_plan (reuse deterministic builder + optional AI summary) ───────
    week_ago = datetime.utcnow().date() - timedelta(days=7)
    latest_ref_result = await session.execute(
        select(WeeklyReflection)
        .where(and_(
            WeeklyReflection.user_id == user.id,
            WeeklyReflection.status == "completed",
            WeeklyReflection.week_start >= week_ago,
        ))
        .order_by(WeeklyReflection.week_start.desc())
        .limit(1)
    )
    latest_ref = latest_ref_result.scalar_one_or_none()
    top_priorities: Optional[list] = None
    if latest_ref and latest_ref.raw_answers:
        top_priorities = (latest_ref.raw_answers or {}).get("top_priorities") or None

    plan = _build_deterministic_daily_plan(
        tasks, routines, completed_routine_ids_set, events, today, top_priorities,
        now_dt=now,
    )
    generated_by = "deterministic"

    try:
        from bot.ai.client import openai_client as _oai
        top_tasks_text = "\n".join(
            f"- [P{t.priority}] {t.title}" for t in sorted(tasks, key=lambda t: t.priority)[:6]
        ) or "None"
        routines_text = "\n".join(
            f"- {r.title}" + (" (done)" if r.id in completed_routine_ids_set else "")
            for r in routines[:5]
        ) or "None"
        events_text = "\n".join(
            f"- {e.start_time.strftime('%H:%M')} {e.title}" for e in events[:5]
        ) or "None"
        prompt = (
            f"Today is {today}. Write one crisp sentence (max 20 words) summarising the day ahead "
            f"based on: tasks: {top_tasks_text} | routines: {routines_text} | events: {events_text}."
        )
        ai_resp = await _asyncio.wait_for(
            _oai.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=60,
                temperature=0.4,
            ),
            timeout=8.0,
        )
        ai_text = (ai_resp.choices[0].message.content or "").strip()
        if ai_text:
            plan["summary"] = ai_text
            generated_by = "ai"
    except Exception as exc:
        _logger.debug("snapshot AI summary skipped: %s", exc)

    # ── 3. next_action ──────────────────────────────────────────────────────────
    next_action = None
    if next_action_task:
        obj_id = next_action_task.get("objective_id")
        if obj_id and not next_action_task.get("objective_title"):
            obj_row = await session.get(Objective, obj_id)
            if obj_row:
                next_action_task = {**next_action_task, "objective_title": obj_row.title}
        next_action = {
            **next_action_task,
            "type": "task",
            "reason": _compute_next_action_reason(next_action_task, today),
        }

    # ── 4. blockers: open tasks blocked by other open tasks ─────────────────────
    blockers: list[dict] = []
    if task_ids:
        rel_res = await session.execute(
            select(NodeRelation).where(
                and_(
                    NodeRelation.user_id == user.id,
                    or_(
                        and_(
                            NodeRelation.relation_type == "blocks",
                            NodeRelation.from_type == "task",
                            NodeRelation.from_id.in_(task_ids),
                            NodeRelation.to_type == "task",
                            NodeRelation.to_id.in_(task_ids),
                        ),
                        and_(
                            NodeRelation.relation_type == "depends_on",
                            NodeRelation.from_type == "task",
                            NodeRelation.from_id.in_(task_ids),
                            NodeRelation.to_type == "task",
                            NodeRelation.to_id.in_(task_ids),
                        ),
                    ),
                )
            )
        )
        block_rels = list(rel_res.scalars().all())

        blocked_map: dict[int, list[dict]] = defaultdict(list)
        for rel in block_rels:
            if rel.relation_type == "blocks":
                # from_task blocks to_task
                blocker_task = task_by_id.get(rel.from_id)
                blocked_map[rel.to_id].append({
                    "type": "task",
                    "id": rel.from_id,
                    "title": blocker_task.title if blocker_task else None,
                })
            elif rel.relation_type == "depends_on":
                # from_task depends_on to_task → from_task is blocked by to_task
                blocker_task = task_by_id.get(rel.to_id)
                blocked_map[rel.from_id].append({
                    "type": "task",
                    "id": rel.to_id,
                    "title": blocker_task.title if blocker_task else None,
                })

        for blocked_id, blocker_refs in blocked_map.items():
            t = task_by_id.get(blocked_id)
            if t:
                blockers.append({
                    "task_id": blocked_id,
                    "task_title": t.title,
                    "blocked_by": blocker_refs,
                })

    # ── 5. suggestions: top pending suggestion notifications (read-only) ─────────
    suggestions_res = await session.execute(
        select(AutopilotNotification)
        .where(and_(
            AutopilotNotification.user_id == user.id,
            AutopilotNotification.notification_type == "suggestion",
            AutopilotNotification.status == "pending",
        ))
        .order_by(AutopilotNotification.created_at.desc())
        .limit(5)
    )
    suggestions = [
        {
            "notification_id": n.id,
            "type": "suggestion",
            "message": n.body,
            "title": n.title,
        }
        for n in suggestions_res.scalars().all()
    ]

    # ── 6. progress_summary ─────────────────────────────────────────────────────
    completed_today_res = await session.execute(
        select(func.count(Task.id)).where(and_(
            Task.user_id == user.id,
            Task.completed_at.is_not(None),
            Task.completed_at >= datetime.combine(today, datetime.min.time()),
        ))
    )
    active_obj_res = await session.execute(
        select(func.count(Objective.id)).where(
            and_(Objective.user_id == user.id, Objective.status == "active")
        )
    )
    rem_count_res = await session.execute(
        select(func.count(ScheduledReminder.id)).where(and_(
            ScheduledReminder.user_id == user.id,
            ScheduledReminder.status == "pending",
            ScheduledReminder.scheduled_for >= now,
        ))
    )
    nudge_count_res = await session.execute(
        select(func.count(AutopilotNotification.id)).where(and_(
            AutopilotNotification.user_id == user.id,
            AutopilotNotification.status == "pending",
        ))
    )

    routines_done = len(completed_routine_ids_set & {r.id for r in routines})
    routines_pending = len([r for r in routines if r.id not in completed_routine_ids_set])

    source_type = "ai" if generated_by == "ai" else "deterministic_fallback"
    confidence_level = "medium" if generated_by == "ai" else "high"
    confidence_reason = (
        "AI-Zusammenfassung auf deterministischem Plan" if generated_by == "ai"
        else "Regelbasierter Snapshot aus Tasks, Routinen und Kalender"
    )

    return {
        "date": today.isoformat(),
        "generated_by": generated_by,
        # Epic 4.2 trust signals (additive)
        "source_type": source_type,
        "confidence_level": confidence_level,
        "confidence_reason": confidence_reason,
        "next_action": next_action,
        "today_plan": {
            "date": today.isoformat(),
            "generated_by": generated_by,
            "source_type": source_type,
            "confidence_level": confidence_level,
            "confidence_reason": confidence_reason,
            **plan,
        },
        "blockers": blockers,
        "suggestions": suggestions,
        "progress_summary": {
            "completed_today": int(completed_today_res.scalar() or 0),
            "open_tasks": len(tasks),
            "active_objectives": int(active_obj_res.scalar() or 0),
            "routines_done": routines_done,
            "routines_pending": routines_pending,
            "pending_reminders": int(rem_count_res.scalar() or 0),
            "pending_nudges": int(nudge_count_res.scalar() or 0),
        },
    }


@router.get("/autopilot/free-slots")
async def get_free_slots(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Epic 2.2 — Calendar-aware free-slot plan for today.

    Returns:
    - windows: all free time windows in working hours (08:00–21:00)
    - suggested_blocks: best-fit tasks matched to realistic slots
    - free_minutes_total / free_minutes_used: time budget overview
    - fallback: true when calendar data is absent (suggestions are priority-only)
    - data_quality: "good" | "no_events" | "no_tasks" | "poor"

    Each suggested block includes:
    - start_time / end_time / duration_minutes
    - window_type: large/medium/small
    - is_near_meeting: true when slot is adjacent to a calendar event
    - task_id / task_title / task_priority
    - slot_reason: why this slot fits
    - task_reason: why this task was chosen (urgency, leverage, priority)
    - confidence: "high" | "medium" | "low"

    This endpoint is additive — existing /autopilot/* endpoints unchanged.
    """
    import asyncio as _asyncio
    from datetime import timezone as _tz
    from bot.core.calendar import get_todays_events as _get_events
    from bot.core.free_slot_planner import plan_free_slots as _plan_slots

    today = date.today()
    now = datetime.now(tz=_tz.utc).replace(tzinfo=None)

    tasks_result, events = await _asyncio.gather(
        session.execute(
            select(Task)
            .where(and_(
                Task.user_id == user.id,
                Task.status.in_(["todo", "in_progress"]),
                Task.category != "shopping",
            ))
            .order_by(Task.priority.asc(), Task.due_date.asc().nulls_last())
        ),
        _get_events(session, user.id),
    )
    tasks = list(tasks_result.scalars().all())
    task_ids = [t.id for t in tasks]

    # ── Optional: enrich with graph leverage data ────────────────────────────
    graph_data: dict[int, dict] = {}
    if task_ids:
        rel_res = await session.execute(
            select(NodeRelation).where(and_(
                NodeRelation.user_id == user.id,
                NodeRelation.from_type == "task",
                NodeRelation.from_id.in_(task_ids),
            ))
        )
        rels = list(rel_res.scalars().all())
        for rel in rels:
            tid = rel.from_id
            if tid not in graph_data:
                graph_data[tid] = {"unlocks_count": 0, "contributes_to": []}
            if rel.relation_type in ("unlocks", "blocks"):
                graph_data[tid]["unlocks_count"] = graph_data[tid]["unlocks_count"] + 1
            elif rel.relation_type == "contributes_to":
                graph_data[tid]["contributes_to"].append({
                    "type": rel.to_type,
                    "id": rel.to_id,
                })

    slot_plan = _plan_slots(
        events=events,
        tasks=tasks,
        today=today,
        now_dt=now,
        graph_data=graph_data,
    )

    return {
        "date": today.isoformat(),
        **slot_plan,
    }


@router.get("/autopilot/daily-plan")
async def get_daily_plan(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Compose today's plan from tasks + routines + calendar + priorities.

    Returns structured sections + suggested blocks for mobile consumption.
    Tries an AI summary; falls back to deterministic output if AI unavailable.
    """
    import asyncio as _asyncio
    import logging as _log
    from bot.core.calendar import get_todays_events as _get_events
    from bot.core.routines import get_todays_completions as _get_completions

    _logger = _log.getLogger(__name__)
    today = date.today()
    now = datetime.utcnow()

    # Fetch data in parallel
    tasks_result, routines_result, completed_ids, events = await _asyncio.gather(
        session.execute(
            select(Task)
            .options(
                selectinload(Task.key_result).selectinload(KeyResult.objective),
                selectinload(Task.objective),
            )
            .where(and_(
                Task.user_id == user.id,
                Task.status.in_(["todo", "in_progress"]),
                Task.category != "shopping",
            ))
            .order_by(Task.priority.asc(), Task.due_date.asc().nulls_last())
        ),
        session.execute(
            select(Routine)
            .where(and_(Routine.user_id == user.id, Routine.status == "active"))
            .order_by(Routine.sort_order, Routine.id)
        ),
        _get_completions(session, user.id),
        _get_events(session, user.id),
    )

    tasks = list(tasks_result.scalars().all())
    routines = list(routines_result.scalars().all())
    completed_routine_ids: set[int] = set(completed_ids) if completed_ids else set()

    # P2.1: Fetch top_priorities from latest reflection in last 7 days
    week_ago = datetime.utcnow().date() - timedelta(days=7)
    latest_ref_result = await session.execute(
        select(WeeklyReflection)
        .where(and_(
            WeeklyReflection.user_id == user.id,
            WeeklyReflection.status == "completed",
            WeeklyReflection.week_start >= week_ago,
        ))
        .order_by(WeeklyReflection.week_start.desc())
        .limit(1)
    )
    latest_ref = latest_ref_result.scalar_one_or_none()
    top_priorities: Optional[list] = None
    if latest_ref and latest_ref.raw_answers:
        top_priorities = (latest_ref.raw_answers or {}).get("top_priorities") or None

    plan = _build_deterministic_daily_plan(
        tasks, routines, completed_routine_ids, events, today, top_priorities,
        now_dt=now,
    )
    generated_by = "deterministic"

    # Optional AI summary (non-blocking, 8s timeout)
    try:
        from bot.ai.client import openai_client as _oai
        top_tasks_text = "\n".join(
            f"- [P{t.priority}] {t.title}" + (f" (due {t.due_date})" if t.due_date else "")
            for t in sorted(tasks, key=lambda t: t.priority)[:6]
        ) or "None"
        routines_text = "\n".join(
            f"- {r.title}" + (" (done)" if r.id in completed_routine_ids else "")
            for r in routines[:5]
        ) or "None"
        events_text = "\n".join(
            f"- {e.start_time.strftime('%H:%M')} {e.title}" for e in events[:5]
        ) or "None"
        prompt = (
            f"Today is {today}. Write one crisp sentence (max 20 words) summarising the day ahead "
            f"based on: tasks: {top_tasks_text} | routines: {routines_text} | events: {events_text}."
        )
        ai_resp = await _asyncio.wait_for(
            _oai.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=60,
                temperature=0.4,
            ),
            timeout=8.0,
        )
        ai_text = (ai_resp.choices[0].message.content or "").strip()
        if ai_text:
            plan["summary"] = ai_text
            generated_by = "ai"
    except Exception as exc:
        _logger.debug("daily-plan AI summary skipped: %s", exc)

    source_type = "ai" if generated_by == "ai" else "deterministic_fallback"
    confidence_level = "medium" if generated_by == "ai" else "high"
    confidence_reason = (
        "AI-Zusammenfassung auf deterministischem Plan" if generated_by == "ai"
        else "Regelbasierter Plan aus Tasks, Routinen und Kalender"
    )

    return {
        "date": today.isoformat(),
        "generated_by": generated_by,
        # Epic 4.2 trust signals (additive)
        "source_type": source_type,
        "confidence_level": confidence_level,
        "confidence_reason": confidence_reason,
        **plan,
    }


@router.get("/autopilot/suggestions")
async def get_autopilot_suggestions(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """P2.3 — Generate and return daily proactive suggestions, enqueuing each as a notification."""
    from bot.core.suggestions import generate_daily_suggestions as _gen_suggestions
    from bot.core.notifications import enqueue_notification as _enqueue
    from datetime import datetime as _dt, timezone as _tz

    raw = await _gen_suggestions(session, user.id)

    result = []
    for item in raw:
        notif = await _enqueue(
            session,
            user_id=user.id,
            notification_type="suggestion",
            body=item["message"],
            title=item["type"].replace("_", " ").title(),
            source="autopilot",
        )
        entry = {
            "type": item["type"],
            "message": item["message"],
            "action_hint": item["action_hint"],
            "notification_id": notif.id if notif else None,
            # Epic 4.2 trust signals (additive)
            "source_type": "deterministic_fallback",
            "confidence_level": "medium",
            "confidence_reason": "Regelbasierter Nudge aus Verhaltensmustern",
        }
        result.append(entry)

    await session.commit()
    return {
        "suggestions": result,
        "generated_at": _dt.now(tz=_tz.utc).isoformat(),
    }


@router.post("/notifications/{notification_id}/snooze")
async def snooze_notification(
    notification_id: int,
    body: SnoozeRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Snooze a notification for N minutes (default 60)."""
    from datetime import timezone as _tz
    if body.minutes < 1 or body.minutes > 10080:  # max 1 week
        raise HTTPException(status_code=400, detail="minutes must be between 1 and 10080")

    result = await session.execute(
        select(AutopilotNotification).where(
            and_(
                AutopilotNotification.id == notification_id,
                AutopilotNotification.user_id == user.id,
            )
        )
    )
    notification = result.scalar_one_or_none()
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")

    now = datetime.now(tz=_tz.utc).replace(tzinfo=None)
    notification.status = "snoozed"
    notification.snoozed_until = now + timedelta(minutes=body.minutes)
    await session.flush()
    return {"ok": True, "notification": _notification_dict(notification)}


# ─── Action Queue Endpoints (A3) ───────────────────────────────────────────────

# Valid states and allowed transitions:
#   planned  → suggested
#   suggested → accepted | snoozed
#   accepted  → completed | snoozed
#   snoozed  → suggested  (when snooze expires, or manual re-surface)
_VALID_STATES = {"planned", "suggested", "accepted", "completed", "snoozed"}
_ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "planned":   {"suggested"},
    "suggested": {"accepted", "snoozed"},
    "accepted":  {"completed", "snoozed"},
    "snoozed":   {"suggested"},
    "completed": set(),
}


def _queue_item_dict(item: ActionQueueItem) -> dict:
    return {
        "id": item.id,
        "state": item.state,
        "item_type": item.item_type,
        "title": item.title,
        "description": item.description,
        "reason": item.reason,
        "linked_task_id": item.linked_task_id,
        "snoozed_until": item.snoozed_until.isoformat() if item.snoozed_until else None,
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
    }


class ActionQueueItemCreate(BaseModel):
    title: str
    description: Optional[str] = None
    reason: Optional[str] = None
    item_type: str = "task"
    linked_task_id: Optional[int] = None


@router.post("/autopilot/action-queue")
async def create_action_queue_item(
    body: ActionQueueItemCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Create a new action queue item. State defaults to 'planned'."""
    item = ActionQueueItem(
        user_id=user.id,
        title=body.title,
        description=body.description,
        reason=body.reason,
        item_type=body.item_type,
        linked_task_id=body.linked_task_id,
        state="planned",
        created_at=datetime.utcnow(),
    )
    session.add(item)
    await session.flush()
    return {"ok": True, "item": _queue_item_dict(item)}


@router.get("/autopilot/action-queue")
async def list_action_queue(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    state: Optional[str] = Query(None, description="Filter by state. Omit for active (non-completed) items."),
    limit: int = Query(50, ge=1, le=200),
) -> dict:
    """List action queue items for the current user.

    Returns active (non-completed) items by default.
    Pass state=all for every item, or a specific state to filter.
    Also returns counts per state for dashboard display.
    """
    from datetime import timezone as _tz
    now = datetime.now(tz=_tz.utc).replace(tzinfo=None)

    # Auto-unsnoze expired items before returning
    expired_result = await session.execute(
        select(ActionQueueItem).where(
            and_(
                ActionQueueItem.user_id == user.id,
                ActionQueueItem.state == "snoozed",
                ActionQueueItem.snoozed_until <= now,
            )
        )
    )
    for item in expired_result.scalars().all():
        item.state = "suggested"
    await session.flush()

    # Build filter
    if state == "all":
        where_clause = ActionQueueItem.user_id == user.id
    elif state in _VALID_STATES:
        where_clause = and_(
            ActionQueueItem.user_id == user.id,
            ActionQueueItem.state == state,
        )
    else:
        # Default: active items (not completed)
        where_clause = and_(
            ActionQueueItem.user_id == user.id,
            ActionQueueItem.state != "completed",
        )

    items_result = await session.execute(
        select(ActionQueueItem)
        .where(where_clause)
        .order_by(ActionQueueItem.created_at.desc())
        .limit(limit)
    )
    items = list(items_result.scalars().all())

    # Counts per state
    counts_result = await session.execute(
        select(ActionQueueItem.state, func.count(ActionQueueItem.id))
        .where(ActionQueueItem.user_id == user.id)
        .group_by(ActionQueueItem.state)
    )
    counts: dict[str, int] = {row[0]: row[1] for row in counts_result.all()}
    counts_by_state = {s: counts.get(s, 0) for s in _VALID_STATES}

    return {
        "items": [_queue_item_dict(i) for i in items],
        "counts": counts_by_state,
        "total_active": sum(counts.get(s, 0) for s in ("planned", "suggested", "accepted")),
    }


class ActionQueueStateUpdate(BaseModel):
    state: str
    snooze_minutes: int = 60  # used when transitioning to snoozed


@router.patch("/autopilot/action-queue/{item_id}")
async def update_action_queue_state(
    item_id: int,
    body: ActionQueueStateUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Update the state of an action queue item (idempotent).

    Allowed transitions:
      planned  → suggested
      suggested → accepted | snoozed
      accepted  → completed | snoozed
      snoozed  → suggested
    Transitioning to the current state is a no-op (idempotent).
    """
    from datetime import timezone as _tz

    new_state = body.state
    if new_state not in _VALID_STATES:
        raise HTTPException(status_code=400, detail=f"Invalid state '{new_state}'. Valid: {sorted(_VALID_STATES)}")

    result = await session.execute(
        select(ActionQueueItem).where(
            and_(
                ActionQueueItem.id == item_id,
                ActionQueueItem.user_id == user.id,
            )
        )
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Action queue item not found")

    # Idempotent: already in target state
    if item.state == new_state:
        return {"ok": True, "item": _queue_item_dict(item), "changed": False}

    allowed = _ALLOWED_TRANSITIONS.get(item.state, set())
    if new_state not in allowed:
        raise HTTPException(
            status_code=422,
            detail=f"Cannot transition from '{item.state}' to '{new_state}'. Allowed: {sorted(allowed) or 'none'}",
        )

    item.state = new_state
    item.updated_at = datetime.utcnow()
    if new_state == "snoozed":
        minutes = max(1, min(body.snooze_minutes, 10080))
        now = datetime.now(tz=_tz.utc).replace(tzinfo=None)
        item.snoozed_until = now + timedelta(minutes=minutes)
    else:
        item.snoozed_until = None

    await session.flush()

    response: dict = {"ok": True, "item": _queue_item_dict(item), "changed": True}

    if new_state == "accepted":
        from bot.core.completion_hooks import get_next_unblocked_action as _get_next
        next_action = await _get_next(session, user.id)
        if next_action:
            response["next_action"] = next_action

    elif new_state == "completed":
        from bot.core.completion_hooks import (
            check_objective_auto_complete as _check_obj,
            get_next_unblocked_action as _get_next,
            update_kr_on_task_complete as _update_kr,
        )
        if item.linked_task_id:
            task_res = await session.execute(
                select(Task).where(Task.id == item.linked_task_id)
            )
            linked_task = task_res.scalar_one_or_none()
            if linked_task and linked_task.status != "done":
                # Mark the linked task done and run KR/objective hooks
                linked_task.status = "done"
                linked_task.completed_at = datetime.utcnow()
                await session.flush()
                kr_updated = await _update_kr(session, linked_task)
                if kr_updated:
                    response["kr_progress"] = {
                        "id": kr_updated.id,
                        "current_value": kr_updated.current_value,
                        "target_value": kr_updated.target_value,
                        "status": kr_updated.status,
                    }
                if linked_task.objective_id:
                    obj_completed = await _check_obj(session, linked_task.objective_id)
                    if obj_completed:
                        response["objective_completed"] = linked_task.objective_id
        next_action = await _get_next(session, user.id)
        if next_action:
            response["next_action"] = next_action

    return response


@router.post("/autopilot/action-engine/run")
async def trigger_action_engine(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    phase: str = Query("morning", description="morning, evening, or weekly"),
) -> dict:
    """Manually trigger the action engine for testing/debugging."""
    from bot.core.action_engine import run_morning_actions, run_evening_actions, run_weekly_actions
    if phase == "morning":
        report = await run_morning_actions(session, user.id)
    elif phase == "evening":
        report = await run_evening_actions(session, user.id)
    elif phase == "weekly":
        report = await run_weekly_actions(session, user.id)
    else:
        raise HTTPException(status_code=400, detail="phase must be morning, evening, or weekly")
    await session.commit()
    return {
        "ok": True,
        "phase": phase,
        "rules_fired": report.rules_fired,
        "tasks_created": report.tasks_created,
        "notifications_created": report.notifications_created,
        "flags_set": report.flags_set,
    }


# ─── Objective Task Suggestions (B3) ───────────────────────────────────────────

# Deterministic fallback task templates per objective category
_CATEGORY_TASK_TEMPLATES: dict[str, list[dict]] = {
    "health": [
        {"title": "Schedule a health check-up", "priority": 2, "reason": "Preventive health baseline"},
        {"title": "Research and choose a health metric to track weekly", "priority": 3, "reason": "Measure progress"},
        {"title": "Build a 4-week habit plan for this goal", "priority": 2, "reason": "Structure drives results"},
        {"title": "Log baseline measurement for this objective", "priority": 3, "reason": "Track from day 1"},
    ],
    "fitness": [
        {"title": "Define weekly training schedule", "priority": 2, "reason": "Consistency requires a plan"},
        {"title": "Set a measurable performance baseline", "priority": 2, "reason": "Benchmark for progress"},
        {"title": "Schedule first session this week", "priority": 1, "reason": "Start immediately"},
        {"title": "Research best approach for this fitness goal", "priority": 3, "reason": "Informed execution"},
    ],
    "business": [
        {"title": "Define the first milestone and deadline", "priority": 1, "reason": "Clear short-term target"},
        {"title": "Identify top 3 blockers for this objective", "priority": 2, "reason": "Remove friction early"},
        {"title": "Draft action plan with weekly checkpoints", "priority": 2, "reason": "Structured execution"},
        {"title": "Review resources and capacity needed", "priority": 3, "reason": "Avoid surprises"},
    ],
    "finance": [
        {"title": "Review current financial baseline for this goal", "priority": 1, "reason": "Know your starting point"},
        {"title": "Set monthly savings or progress target", "priority": 2, "reason": "Incremental progress"},
        {"title": "Identify one recurring expense to reduce", "priority": 3, "reason": "Free up resources"},
        {"title": "Set up tracking system for this objective", "priority": 2, "reason": "What gets measured gets done"},
    ],
    "learning": [
        {"title": "Find the best resource (book/course) for this topic", "priority": 2, "reason": "Start with the right input"},
        {"title": "Block 30 minutes daily for focused learning", "priority": 1, "reason": "Consistency compounds"},
        {"title": "Define what 'done' looks like for this learning goal", "priority": 2, "reason": "Clear success criteria"},
        {"title": "Share or apply one thing learned each week", "priority": 3, "reason": "Learning by doing"},
    ],
    "personal": [
        {"title": "Write down why this goal matters to you", "priority": 3, "reason": "Motivation anchor"},
        {"title": "Break objective into 3 concrete milestones", "priority": 1, "reason": "Clarity drives action"},
        {"title": "Schedule weekly 15-minute review for this objective", "priority": 2, "reason": "Stay on track"},
        {"title": "Identify one person who can support or hold you accountable", "priority": 3, "reason": "Social commitment"},
    ],
}
_DEFAULT_TEMPLATES = [
    {"title": "Define the first concrete action step", "priority": 1, "reason": "Start with clarity"},
    {"title": "Set a measurable milestone for this objective", "priority": 2, "reason": "Track progress"},
    {"title": "Review progress weekly and adjust plan", "priority": 3, "reason": "Consistent reflection"},
]


def _suggestion_dict(s: ObjectiveTaskSuggestion) -> dict:
    return {
        "id": s.id,
        "objective_id": s.objective_id,
        "title": s.title,
        "description": s.description,
        "priority": s.priority,
        "reason": s.reason,
        "status": s.status,
        "accepted_task_id": s.accepted_task_id,
        "created_at": s.created_at.isoformat(),
    }


@router.post("/objectives/{objective_id}/generate-tasks")
async def generate_objective_tasks(
    objective_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Generate suggested tasks for an objective via AI (GPT-4o) with deterministic fallback.

    Suggestions are saved with status='pending' and do NOT become active tasks until accepted.
    Existing pending suggestions are replaced to avoid duplicates.
    """
    import asyncio as _asyncio
    import json as _json
    import logging as _log

    _logger = _log.getLogger(__name__)

    # Fetch objective (must belong to user)
    obj_result = await session.execute(
        select(Objective)
        .options(selectinload(Objective.key_results))
        .where(and_(Objective.id == objective_id, Objective.user_id == user.id))
    )
    obj = obj_result.scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="Objective not found")

    # Delete existing pending suggestions to start fresh
    existing_result = await session.execute(
        select(ObjectiveTaskSuggestion).where(
            and_(
                ObjectiveTaskSuggestion.objective_id == objective_id,
                ObjectiveTaskSuggestion.user_id == user.id,
                ObjectiveTaskSuggestion.status == "pending",
            )
        )
    )
    for old in existing_result.scalars().all():
        await session.delete(old)
    await session.flush()

    # Build key result context for AI
    kr_text = "; ".join(kr.title for kr in obj.key_results if kr.status == "active") or "none"
    desc_text = obj.description or ""

    raw_suggestions: list[dict] = []
    generated_by = "deterministic"

    # Try AI generation first
    try:
        from bot.ai.client import openai_client as _oai

        prompt = (
            f"You are a personal productivity coach. Generate exactly 4 concrete, actionable tasks "
            f"for the following objective.\n\n"
            f"Objective: {obj.title}\n"
            f"Category: {obj.category}\n"
            f"Description: {desc_text or '(none)'}\n"
            f"Key Results: {kr_text}\n\n"
            "Return a JSON array (no other text) with exactly 4 items, each with:\n"
            '  "title": string (max 80 chars, action verb start),\n'
            '  "priority": integer 1-3 (1=highest),\n'
            '  "reason": string (one sentence why this task matters for the objective)\n\n'
            "Make tasks specific, measurable, and immediately actionable. No fluff."
        )

        ai_response = await _asyncio.wait_for(
            _oai.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=600,
                temperature=0.4,
            ),
            timeout=12.0,
        )
        raw = (ai_response.choices[0].message.content or "").strip()
        # Extract JSON array robustly
        import re as _re
        match = _re.search(r"\[.*\]", raw, _re.DOTALL)
        if match:
            parsed = _json.loads(match.group())
            if isinstance(parsed, list):
                for item in parsed[:5]:
                    if isinstance(item, dict) and item.get("title"):
                        raw_suggestions.append({
                            "title": str(item["title"])[:500],
                            "priority": int(item.get("priority", 3)),
                            "reason": str(item.get("reason", ""))[:500],
                        })
                if raw_suggestions:
                    generated_by = "ai"
    except Exception as exc:
        _logger.debug("AI task generation failed, using fallback: %s", exc)

    # Deterministic fallback
    if not raw_suggestions:
        templates = _CATEGORY_TASK_TEMPLATES.get(obj.category, _DEFAULT_TEMPLATES)
        for t in templates:
            raw_suggestions.append({
                "title": t["title"],
                "priority": t["priority"],
                "reason": t["reason"],
            })

    # Persist suggestions
    suggestions = []
    for item in raw_suggestions:
        s = ObjectiveTaskSuggestion(
            user_id=user.id,
            objective_id=objective_id,
            title=item["title"],
            priority=max(1, min(5, item.get("priority", 3))),
            reason=item.get("reason") or None,
            status="pending",
        )
        session.add(s)
        suggestions.append(s)

    await session.flush()

    return {
        "objective_id": objective_id,
        "generated_by": generated_by,
        "suggestions": [_suggestion_dict(s) for s in suggestions],
        "count": len(suggestions),
    }


@router.get("/objectives/{objective_id}/suggestions")
async def list_objective_suggestions(
    objective_id: int,
    status: Optional[str] = Query(None, description="Filter by status: pending, accepted, rejected. Omit for all."),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """List task suggestions for a specific objective."""
    # Verify objective belongs to user
    obj_result = await session.execute(
        select(Objective).where(and_(Objective.id == objective_id, Objective.user_id == user.id))
    )
    if not obj_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Objective not found")

    conditions = [
        ObjectiveTaskSuggestion.objective_id == objective_id,
        ObjectiveTaskSuggestion.user_id == user.id,
    ]
    if status in ("pending", "accepted", "rejected"):
        conditions.append(ObjectiveTaskSuggestion.status == status)

    result = await session.execute(
        select(ObjectiveTaskSuggestion)
        .where(and_(*conditions))
        .order_by(ObjectiveTaskSuggestion.priority.asc(), ObjectiveTaskSuggestion.created_at.asc())
    )
    suggestions = result.scalars().all()
    return {"suggestions": [_suggestion_dict(s) for s in suggestions], "count": len(suggestions)}


@router.get("/task-suggestions")
async def list_all_pending_suggestions(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    status: Optional[str] = Query("pending", description="Filter by status: pending, accepted, rejected, all"),
    limit: int = Query(50, ge=1, le=200),
) -> dict:
    """List task suggestions across all objectives (primarily for mobile review flow)."""
    conditions = [ObjectiveTaskSuggestion.user_id == user.id]
    if status != "all":
        filter_status = status if status in ("pending", "accepted", "rejected") else "pending"
        conditions.append(ObjectiveTaskSuggestion.status == filter_status)

    result = await session.execute(
        select(ObjectiveTaskSuggestion)
        .options(selectinload(ObjectiveTaskSuggestion.objective))
        .where(and_(*conditions))
        .order_by(ObjectiveTaskSuggestion.priority.asc(), ObjectiveTaskSuggestion.created_at.desc())
        .limit(limit)
    )
    suggestions = result.scalars().all()

    return {
        "suggestions": [
            {
                **_suggestion_dict(s),
                "objective_title": s.objective.title if s.objective else None,
            }
            for s in suggestions
        ],
        "count": len(suggestions),
        "pending_count": sum(1 for s in suggestions if s.status == "pending"),
    }


@router.post("/task-suggestions/{suggestion_id}/accept")
async def accept_task_suggestion(
    suggestion_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Accept a task suggestion — creates a real Task linked to the objective.

    The suggestion status becomes 'accepted' and accepted_task_id is set.
    Idempotent: re-accepting returns the already-created task.
    """
    result = await session.execute(
        select(ObjectiveTaskSuggestion).where(
            and_(
                ObjectiveTaskSuggestion.id == suggestion_id,
                ObjectiveTaskSuggestion.user_id == user.id,
            )
        )
    )
    suggestion = result.scalar_one_or_none()
    if not suggestion:
        raise HTTPException(status_code=404, detail="Suggestion not found")

    if suggestion.status == "accepted" and suggestion.accepted_task_id:
        # Idempotent: already accepted
        task_result = await session.execute(
            select(Task).where(Task.id == suggestion.accepted_task_id)
        )
        task = task_result.scalar_one_or_none()
        return {
            "ok": True,
            "already_accepted": True,
            "suggestion": _suggestion_dict(suggestion),
            "task": {"id": task.id, "title": task.title} if task else None,
        }

    if suggestion.status == "rejected":
        raise HTTPException(status_code=422, detail="Cannot accept a rejected suggestion. Generate new suggestions.")

    # Create the real task
    task = Task(
        user_id=user.id,
        objective_id=suggestion.objective_id,
        title=suggestion.title,
        description=suggestion.description,
        priority=suggestion.priority,
        status="todo",
        category="general",
    )
    session.add(task)
    await session.flush()

    suggestion.status = "accepted"
    suggestion.accepted_task_id = task.id
    await session.flush()

    return {
        "ok": True,
        "already_accepted": False,
        "suggestion": _suggestion_dict(suggestion),
        "task": {"id": task.id, "title": task.title, "objective_id": task.objective_id},
    }


@router.post("/task-suggestions/{suggestion_id}/reject")
async def reject_task_suggestion(
    suggestion_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Reject a task suggestion — marks it rejected without creating a task.

    Idempotent: re-rejecting is a no-op.
    """
    result = await session.execute(
        select(ObjectiveTaskSuggestion).where(
            and_(
                ObjectiveTaskSuggestion.id == suggestion_id,
                ObjectiveTaskSuggestion.user_id == user.id,
            )
        )
    )
    suggestion = result.scalar_one_or_none()
    if not suggestion:
        raise HTTPException(status_code=404, detail="Suggestion not found")

    if suggestion.status == "accepted":
        raise HTTPException(status_code=422, detail="Cannot reject an already accepted suggestion.")

    suggestion.status = "rejected"
    await session.flush()

    return {"ok": True, "suggestion": _suggestion_dict(suggestion)}


# ── In-app Review Flow (C6) ────────────────────────────────────────────────

class MorningCheckinBody(BaseModel):
    mood: Optional[int] = None          # 1-10
    intentions: Optional[list[str]] = None


class EveningReviewBody(BaseModel):
    day_score: Optional[int] = None     # 1-10
    biggest_win: Optional[str] = None
    learning: Optional[str] = None


@router.post("/autopilot/morning-checkin")
async def morning_checkin(
    body: MorningCheckinBody,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Save morning check-in: mood + top 3 intentions.

    Stores as a Log entry (log_type='morning_checkin') so it appears in
    the activity timeline. Idempotent — creates at most one entry per day.
    """
    today_start = datetime.combine(date.today(), datetime.min.time())
    existing = await session.execute(
        select(Log).where(
            and_(
                Log.user_id == user.id,
                Log.log_type == "morning_checkin",
                Log.logged_at >= today_start,
            )
        )
    )
    if existing.scalar_one_or_none():
        return {"ok": True, "already_done": True}

    mood = max(1, min(10, body.mood)) if body.mood is not None else None
    intentions = [i.strip() for i in (body.intentions or []) if i.strip()]

    log = Log(
        user_id=user.id,
        log_type="morning_checkin",
        data={"mood": mood, "intentions": intentions},
        source="mobile",
        raw_input=None,
    )
    session.add(log)
    await session.flush()
    return {"ok": True, "already_done": False, "log_id": log.id}


@router.post("/autopilot/evening-review")
async def evening_review(
    body: EveningReviewBody,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Save evening review: day score, biggest win, key learning.

    Persists day_score to today's DailyBrief row (creates one if missing)
    and saves a Log entry for the activity timeline.
    """
    today = date.today()
    today_start = datetime.combine(today, datetime.min.time())

    # Upsert DailyBrief
    brief_result = await session.execute(
        select(DailyBrief).where(
            and_(DailyBrief.user_id == user.id, DailyBrief.brief_date == today)
        )
    )
    brief = brief_result.scalar_one_or_none()
    if brief is None:
        brief = DailyBrief(user_id=user.id, brief_date=today)
        session.add(brief)
    if body.day_score is not None:
        brief.day_score = max(1, min(10, body.day_score))

    # Log entry (idempotent: one per day)
    existing_log = await session.execute(
        select(Log).where(
            and_(
                Log.user_id == user.id,
                Log.log_type == "evening_review",
                Log.logged_at >= today_start,
            )
        )
    )
    if not existing_log.scalar_one_or_none():
        log = Log(
            user_id=user.id,
            log_type="evening_review",
            data={
                "day_score": body.day_score,
                "biggest_win": body.biggest_win,
                "learning": body.learning,
            },
            source="mobile",
            raw_input=None,
        )
        session.add(log)

    await session.flush()
    return {"ok": True, "day_score": brief.day_score}


# ─── User Documents (Personal Reference Library) ──────────────────────────────

class CreateDocBody(BaseModel):
    title: str
    emoji: str = "📄"
    content: str = ""
    sort_order: int = 0

class UpdateDocBody(BaseModel):
    title: Optional[str] = None
    emoji: Optional[str] = None
    content: Optional[str] = None
    sort_order: Optional[int] = None


@router.get("/docs")
async def list_docs(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    from bot.database.models import UserDocument
    result = await session.execute(
        select(UserDocument)
        .where(UserDocument.user_id == user.id)
        .order_by(UserDocument.sort_order, UserDocument.id)
    )
    docs = result.scalars().all()
    return {
        "docs": [
            {
                "id": d.id,
                "title": d.title,
                "emoji": d.emoji,
                "content": d.content,
                "sort_order": d.sort_order,
                "created_at": d.created_at.isoformat() if d.created_at else None,
                "updated_at": d.updated_at.isoformat() if d.updated_at else None,
            }
            for d in docs
        ]
    }


@router.post("/docs")
async def create_doc(
    body: CreateDocBody,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    from bot.database.models import UserDocument
    doc = UserDocument(
        user_id=user.id,
        title=body.title,
        emoji=body.emoji,
        content=body.content,
        sort_order=body.sort_order,
    )
    session.add(doc)
    await session.flush()
    return {
        "id": doc.id,
        "title": doc.title,
        "emoji": doc.emoji,
        "content": doc.content,
        "sort_order": doc.sort_order,
        "created_at": doc.created_at.isoformat() if doc.created_at else None,
        "updated_at": doc.updated_at.isoformat() if doc.updated_at else None,
    }


@router.put("/docs/{doc_id}")
async def update_doc(
    doc_id: int,
    body: UpdateDocBody,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    from bot.database.models import UserDocument
    doc = await session.get(UserDocument, doc_id)
    if not doc or doc.user_id != user.id:
        raise HTTPException(status_code=404, detail="Not found")
    if body.title is not None:
        doc.title = body.title
    if body.emoji is not None:
        doc.emoji = body.emoji
    if body.content is not None:
        doc.content = body.content
    if body.sort_order is not None:
        doc.sort_order = body.sort_order
    await session.flush()
    return {
        "id": doc.id,
        "title": doc.title,
        "emoji": doc.emoji,
        "content": doc.content,
        "sort_order": doc.sort_order,
        "created_at": doc.created_at.isoformat() if doc.created_at else None,
        "updated_at": doc.updated_at.isoformat() if doc.updated_at else None,
    }


@router.delete("/docs/{doc_id}")
async def delete_doc(
    doc_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    from bot.database.models import UserDocument
    doc = await session.get(UserDocument, doc_id)
    if not doc or doc.user_id != user.id:
        raise HTTPException(status_code=404, detail="Not found")
    await session.delete(doc)
    return {"ok": True}


# ─── AI Objective Analysis ────────────────────────────────────────────────────

class SetParentBody(BaseModel):
    parent_objective_id: Optional[int] = None


@router.post("/objectives/{objective_id}/set-parent")
async def set_objective_parent(
    objective_id: int,
    body: SetParentBody,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    obj = await session.get(Objective, objective_id)
    if not obj or obj.user_id != user.id:
        raise HTTPException(status_code=404, detail="Not found")
    if body.parent_objective_id and body.parent_objective_id == objective_id:
        raise HTTPException(status_code=400, detail="Cannot be its own parent")
    obj.parent_objective_id = body.parent_objective_id
    await session.flush()
    return {"ok": True, "objective_id": objective_id, "parent_objective_id": obj.parent_objective_id}


@router.get("/objectives/ai-analysis")
async def analyze_objectives(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """AI analyzes all objectives + tasks, returns structure suggestions."""
    import json as _json
    from openai import AsyncOpenAI
    import os

    result = await session.execute(
        select(Objective)
        .where(Objective.user_id == user.id, Objective.status == "active")
        .options(selectinload(Objective.key_results))
    )
    objectives = result.scalars().all()

    tasks_result = await session.execute(
        select(Task).where(Task.user_id == user.id, Task.status == "open").limit(80)
    )
    tasks = tasks_result.scalars().all()

    obj_list = [
        {
            "id": o.id,
            "title": o.title,
            "description": o.description,
            "category": o.category,
            "parent_objective_id": o.parent_objective_id,
            "key_results": [kr.title for kr in o.key_results],
        }
        for o in objectives
    ]
    task_list = [{"id": t.id, "title": t.title, "objective_id": t.objective_id} for t in tasks[:50]]

    if not obj_list:
        return {"parent_suggestions": [], "synergies": [], "overlaps": [], "missing_links": [], "summary": "Keine aktiven Ziele vorhanden."}

    prompt = f"""Du bist ein strategischer Life-Coach. Analysiere diese Ziele und Aufgaben und gib strukturierte Empfehlungen zurueck.

Aktive Ziele:
{_json.dumps(obj_list, ensure_ascii=False, indent=2)}

Offene Aufgaben (Auswahl):
{_json.dumps(task_list, ensure_ascii=False, indent=2)}

Analysiere und erkenne:
1. Hierarchie: Welche Ziele sind Unterziele anderer?
2. Synergien: Welche Ziele ergaenzen sich?
3. Ueberlappungen: Welche Ziele sind zu aehnlich?
4. Fehlende Verbindungen: Welche haengen logisch zusammen?

Antworte NUR mit JSON:
{{
  "parent_suggestions": [
    {{"child_objective_id": int, "child_title": "string", "suggested_parent_id": int, "parent_title": "string", "reason": "kurze Begruendung auf Deutsch"}}
  ],
  "synergies": [
    {{"objective_ids": [int, int], "titles": ["string", "string"], "synergy": "was haben sie gemeinsam"}}
  ],
  "overlaps": [
    {{"objective_ids": [int, int], "titles": ["string", "string"], "overlap": "was ueberschneidet sich", "suggestion": "was tun"}}
  ],
  "missing_links": [
    {{"objective_ids": [int, int], "titles": ["string", "string"], "connection": "warum sie zusammenhaengen"}}
  ],
  "summary": "1-2 Saetze Gesamtbewertung auf Deutsch"
}}"""

    openai_key = os.environ.get("OPENAI_API_KEY", "")
    if not openai_key:
        return {"parent_suggestions": [], "synergies": [], "overlaps": [], "missing_links": [], "summary": "OpenAI API Key nicht konfiguriert."}

    try:
        client = AsyncOpenAI(api_key=openai_key)
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            response_format={"type": "json_object"},
        )
        analysis = _json.loads(response.choices[0].message.content)
        return analysis
    except Exception as e:
        return {
            "parent_suggestions": [],
            "synergies": [],
            "overlaps": [],
            "missing_links": [],
            "summary": f"Analyse fehlgeschlagen: {str(e)}",
        }


# ─── Protocol Endpoints ───────────────────────────────────────────────────────

_SUPPLEMENT_PROTOCOL_PATH = (
    Path(__file__).resolve().parents[2] / "docs" / "protocols" / "lukas_keto_supplements.json"
)
_FITNESS_PROTOCOL_PATH = (
    Path(__file__).resolve().parents[2] / "docs" / "protocols" / "lukas_fitness_split.json"
)


@router.get("/protocols/supplements")
async def get_supplement_protocol(user: User = Depends(get_current_user)) -> dict:
    """Return the supplement protocol JSON."""
    import json as _json
    try:
        return _json.loads(_SUPPLEMENT_PROTOCOL_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Supplement-Protokoll nicht gefunden")


@router.put("/protocols/supplements")
async def update_supplement_protocol(
    payload: dict,
    user: User = Depends(get_current_user),
) -> dict:
    """Overwrite the supplement protocol JSON."""
    import json as _json
    _SUPPLEMENT_PROTOCOL_PATH.write_text(_json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True}


@router.get("/protocols/fitness")
async def get_fitness_protocol(user: User = Depends(get_current_user)) -> dict:
    """Return the fitness split protocol JSON."""
    import json as _json
    try:
        return _json.loads(_FITNESS_PROTOCOL_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Fitness-Protokoll nicht gefunden")


@router.put("/protocols/fitness")
async def update_fitness_protocol(
    payload: dict,
    user: User = Depends(get_current_user),
) -> dict:
    """Overwrite the fitness split protocol JSON."""
    import json as _json
    _FITNESS_PROTOCOL_PATH.write_text(_json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True}


# ─── Goal Coach (AI-powered Goal Wizard) ─────────────────────────────────────

class GoalClarifyBody(BaseModel):
    goal: str


class GoalOptionsBody(BaseModel):
    goal: str
    category: str
    answers: dict


class GoalGenerateBody(BaseModel):
    goal: str
    category: Optional[str] = None
    answers: Optional[dict] = None
    selected_krs: Optional[list] = None
    feedback: Optional[str] = None
    # legacy fields kept for backward compat
    why: Optional[str] = None
    timeframe: Optional[str] = None
    current_state: Optional[str] = None


class GoalRefineBody(BaseModel):
    goal: str
    category: str
    answers: dict
    current_kr_options: list
    feedback: str


def _goal_openai_client() -> "AsyncOpenAI":  # type: ignore[name-defined]
    import os
    from openai import AsyncOpenAI
    key = os.environ.get("OPENAI_API_KEY", "")
    if not key:
        raise HTTPException(status_code=503, detail="OpenAI API Key fehlt auf dem Server.")
    return AsyncOpenAI(api_key=key)


@router.post("/goals/clarify")
async def goal_clarify(
    body: GoalClarifyBody,
    user: User = Depends(get_current_user),
) -> dict:
    """Return goal-category-specific clarifying questions with type/hint/options."""
    import json as _j

    fallback = {
        "category": "personal",
        "category_emoji": "🎯",
        "questions": [
            {"id": "why", "label": "Warum ist dir das wichtig?", "placeholder": "Deine tiefe Motivation...", "hint": "Je klarer deine Motivation, desto höher deine Ausdauer.", "type": "text"},
            {"id": "timeframe", "label": "Bis wann willst du es erreichen?", "placeholder": "z.B. in 3 Monaten", "hint": "Ein Zeitrahmen macht das Ziel planbar.", "type": "choice", "options": ["4 Wochen", "8 Wochen", "3 Monate", "6 Monate", "1 Jahr"]},
            {"id": "current_state", "label": "Wo stehst du gerade?", "placeholder": "Aktueller Stand...", "hint": "Hilft mir die richtige Ausgangsbasis zu setzen.", "type": "text"},
        ],
    }

    try:
        client = _goal_openai_client()
    except HTTPException:
        return fallback

    system = (
        "Du bist ein strategischer Life-Coach. Analysiere das Ziel des Nutzers, "
        "erkenne die Kategorie und stelle sehr präzise, kategoriespezifische Fragen "
        "um das Ziel SMART zu machen. Antworte nur auf Deutsch, nur als JSON."
    )
    prompt = f"""Ziel: "{body.goal}"

Antworte NUR als JSON:
{{
  "category": "fitness|health|business|finance|learning|relationships|personal|creative",
  "category_emoji": "passendes Emoji für die Kategorie",
  "questions": [
    {{
      "id": "eindeutige_id",
      "label": "Präzise Frage (max 70 Zeichen)",
      "placeholder": "Beispielantwort",
      "hint": "Kurze Erklärung warum diese Frage wichtig ist (max 60 Zeichen)",
      "type": "text|choice",
      "options": ["Option1", "Option2"]
    }}
  ]
}}

Regeln:
- Generiere 3-4 Fragen
- Verwende type="choice" mit options wenn sinnvoll (Zeitrahmen, Frequenz, Level)
- Fragen sollen SPEZIFISCH für das Ziel und die Kategorie sein, nicht generisch
- Kategorie-Hints:
  fitness/health: Startgewicht/Kraft-Level, Trainingsfrequenz, spez. Zielmetrik
  business: Aktueller Umsatz/Status, Zielkunde, konkretes Revenue-Ziel
  learning: Vorwissen, Lernzeit täglich, konkretes Anwendungsziel
  finance: Aktuelles Einkommen/Ausgaben, Sparziel, Zeitraum
  relationships: Kontext, gewünschte Veränderung, Frequenz
  creative: Medium/Format, Erfahrung, Output-Ziel"""

    try:
        resp = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
            temperature=0.3,
            response_format={"type": "json_object"},
        )
        return _j.loads(resp.choices[0].message.content)
    except Exception:
        return fallback


@router.post("/goals/generate-options")
async def goal_generate_options(
    body: GoalOptionsBody,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Generate KR options for user to pick from. Returns objective draft + 7-9 KR options."""
    import json as _j
    from datetime import date as _date

    existing_result = await session.execute(
        select(Objective).where(Objective.user_id == user.id, Objective.status == "active")
    )
    existing_titles = [o.title for o in existing_result.scalars().all()]
    today = _date.today().isoformat()
    answers_text = "\n".join(f"- {k}: {v}" for k, v in (body.answers or {}).items() if v)

    system = (
        "Du bist ein OKR-Experte und Life-Coach. Generiere messbare Key Result Optionen "
        "für den Nutzer zum Auswählen. Antworte nur auf Deutsch, nur als JSON."
    )
    prompt = f"""Heute: {today}
Bestehende Ziele: {', '.join(existing_titles) if existing_titles else 'Keine'}

Ziel: "{body.goal}"
Kategorie: {body.category}
Antworten des Nutzers:
{answers_text or 'Keine Antworten gegeben'}

Generiere NUR JSON:
{{
  "objective_draft": {{
    "title": "Inspirierender Titel max 80 Zeichen",
    "description": "1-2 Sätze warum wichtig",
    "category": "{body.category}",
    "target_date": "YYYY-MM-DD",
    "emoji": "passendes Emoji"
  }},
  "motivation_message": "Persönliche motivierende Nachricht 2-3 Sätze",
  "first_step": "Erster konkreter Schritt HEUTE",
  "kr_options": [
    {{
      "id": "kr_eindeutig_1",
      "title": "Messbares KR mit konkretem Zielwert",
      "metric_type": "number|percentage|boolean|streak",
      "target_value": 10,
      "current_value": 0,
      "unit": "Einheit oder null",
      "why": "Warum dieses KR sinnvoll ist (max 60 Zeichen)",
      "recommended": true,
      "difficulty": "easy|medium|hard"
    }}
  ]
}}

Regeln für kr_options:
- Generiere 7-9 verschiedene KR-Optionen
- Markiere 2-3 als recommended: true (die sinnvollste Kombination)
- Verschiedene Schwierigkeitsgrade: mindestens 2 easy, 3-4 medium, 1-2 hard
- KRs sollen sich ERGÄNZEN, nicht doppeln
- Nutze die Antworten des Nutzers für konkrete Zahlen (Ausgangs-/Zielwerte)
- Jedes KR braucht echte, messbare Zahlen"""

    client = _goal_openai_client()
    try:
        resp = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
            temperature=0.4,
            response_format={"type": "json_object"},
        )
        return _j.loads(resp.choices[0].message.content)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"KI-Generierung fehlgeschlagen: {exc}") from exc


@router.post("/goals/refine-options")
async def goal_refine_options(
    body: GoalRefineBody,
    user: User = Depends(get_current_user),
) -> dict:
    """Refine KR options based on user feedback."""
    import json as _j

    current_json = _j.dumps(body.current_kr_options, ensure_ascii=False)
    answers_text = "\n".join(f"- {k}: {v}" for k, v in (body.answers or {}).items() if v)

    system = (
        "Du bist ein OKR-Experte. Verfeinere die Key Result Optionen basierend auf dem "
        "Feedback des Nutzers. Antworte nur auf Deutsch, nur als JSON."
    )
    prompt = f"""Ziel: "{body.goal}" (Kategorie: {body.category})
Nutzer-Antworten: {answers_text or 'keine'}

Aktuelle KR-Optionen:
{current_json}

Nutzer-Feedback: "{body.feedback}"

Generiere eine überarbeitete Liste als JSON:
{{"kr_options": [ ...gleiche Struktur wie oben... ]}}

Regeln:
- Beachte das Feedback und passe die Optionen entsprechend an
- Behalte gute bestehende KRs, ersetze nur was kritisiert wird
- Wieder 7-9 Optionen, 2-3 empfohlen, alle Schwierigkeitsgrade vertreten
- IDs dürfen sich ändern (neue IDs für neue KRs)"""

    client = _goal_openai_client()
    try:
        resp = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
            temperature=0.5,
            response_format={"type": "json_object"},
        )
        return _j.loads(resp.choices[0].message.content)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"KI-Verfeinerung fehlgeschlagen: {exc}") from exc


@router.post("/goals/generate")
async def goal_generate(
    body: GoalGenerateBody,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Generate full plan from selected KRs. Saves as OKRProposalDraft."""
    import json as _json
    from datetime import date as _date

    existing_result = await session.execute(
        select(Objective).where(Objective.user_id == user.id, Objective.status == "active")
    )
    existing_titles = [o.title for o in existing_result.scalars().all()]
    today = _date.today().isoformat()

    # Support both new (selected_krs + answers) and legacy (why/timeframe/current_state) call
    answers_text = ""
    if body.answers:
        answers_text = "\n".join(f"- {k}: {v}" for k, v in body.answers.items() if v)
    else:
        parts = []
        if body.why: parts.append(f"- Warum: {body.why}")
        if body.timeframe: parts.append(f"- Zeitrahmen: {body.timeframe}")
        if body.current_state: parts.append(f"- Aktueller Stand: {body.current_state}")
        answers_text = "\n".join(parts)

    selected_krs_json = _json.dumps(body.selected_krs or [], ensure_ascii=False)

    system = (
        "Du bist ein strategischer Life-Coach und OKR-Experte. "
        "Generiere einen konkreten Aktionsplan basierend auf den bereits festgelegten Key Results. "
        "Antworte auf Deutsch. Sei präzise und actionable."
    )

    if body.selected_krs:
        # New flow: KRs already selected, generate tasks + schedule around them
        user_prompt = f"""Heute: {today}
Bestehende Ziele: {', '.join(existing_titles) if existing_titles else 'Keine'}

Ziel: "{body.goal}" (Kategorie: {body.category or 'general'})
Nutzer-Antworten: {answers_text or 'keine'}
Feedback: {body.feedback or 'keins'}

Bereits ausgewählte Key Results (NICHT ändern):
{selected_krs_json}

Generiere NUR JSON:
{{
  "objective": {{
    "title": "Inspirierender Titel max 80 Zeichen",
    "description": "1-2 Sätze warum wichtig",
    "category": "{body.category or 'personal'}",
    "target_date": "YYYY-MM-DD",
    "emoji": "passendes Emoji"
  }},
  "key_results": {selected_krs_json},
  "tasks": [
    {{"title": "Konkreter Task", "priority": 1, "due_days": 7, "category": "Kategorie", "kr_title": "Exakter Titel des zugehörigen Key Results aus der Liste oben"}}
  ],
  "weekly_schedule": [
    {{"day": "Montag", "activity": "Was tun", "duration_min": 60}}
  ],
  "reminders": [
    {{"title": "Erinnerung", "message": "Push-Text max 80 Zeichen", "day_offset": 1, "time": "08:00", "kr_title": "Zugehöriger KR-Titel"}}
  ],
  "routines": [
    {{"title": "Routine-Titel z.B. 'Tägliches Workout'", "frequency": "täglich|wöchentlich|3x pro Woche", "time_of_day": "morning|evening|anytime", "duration_min": 30, "kr_title": "Zugehöriger KR-Titel"}}
  ],
  "shopping_items": ["Artikel 1", "Artikel 2"],
  "synergies": [
    {{"existing_goal": "Titel des bestehenden Ziels", "connection": "Wie hängt es zusammen"}}
  ],
  "motivation_message": "Persönliche motivierende Nachricht 2-3 Sätze",
  "first_step": "Erster konkreter Schritt HEUTE"
}}

Regeln:
- 5-8 Tasks die DIREKT auf die KRs einzahlen, jeder Task hat kr_title gesetzt
- Wochenplan nur bei regelmäßigen Aktivitäten
- 2-4 Erinnerungen als Push-Benachrichtigungen für die wichtigsten Meilensteine
- Synergien nur wenn wirklich relevant
- Routinen: 1-3 wiederkehrende Gewohnheiten die das Ziel unterstützen (nicht optional — IMMER ausfüllen wenn sinnvoll)
- Shopping-Items: nur konkrete Einkäufe die wirklich nötig sind (z.B. Sportgeräte, Bücher, Zutaten) — leer lassen wenn nicht relevant"""
    else:
        # Legacy flow: generate everything
        user_prompt = f"""Heute: {today}
Bestehende Ziele: {', '.join(existing_titles) if existing_titles else 'Keine'}

Neues Ziel: "{body.goal}"
{answers_text}

Generiere vollständigen OKR-Plan als JSON:
{{
  "objective": {{"title": "max 80 Zeichen", "description": "1-2 Sätze", "category": "fitness|health|business|personal|finance|learning|relationships", "target_date": "YYYY-MM-DD", "emoji": "Emoji"}},
  "key_results": [{{"title": "...", "metric_type": "number|percentage|boolean|streak", "target_value": 10, "current_value": 0, "unit": "...", "why": "...", "recommended": true, "difficulty": "medium"}}],
  "tasks": [{{"title": "...", "priority": 1, "due_days": 7, "category": "..."}}],
  "weekly_schedule": [{{"day": "Montag", "activity": "...", "duration_min": 60}}],
  "routines": [{{"title": "...", "frequency": "täglich|wöchentlich", "time_of_day": "morning|evening|anytime", "duration_min": 30, "kr_title": "..."}}],
  "shopping_items": ["Artikel 1"],
  "synergies": [{{"existing_goal": "...", "connection": "..."}}],
  "motivation_message": "...",
  "first_step": "..."
}}
Regeln: 3-5 KRs, 5-8 Tasks mit due_days (1-90 Tage), Wochenplan + Routinen bei Habit/Sport."""

    client = _goal_openai_client()
    try:
        resp = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user_prompt}],
            temperature=0.4,
            response_format={"type": "json_object"},
        )
        plan = _json.loads(resp.choices[0].message.content)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"KI-Generierung fehlgeschlagen: {exc}") from exc

    draft = OKRProposalDraft(
        user_id=user.id,
        source_text=body.goal,
        draft_payload=plan,
        status="pending",
    )
    session.add(draft)
    await session.flush()

    return {"draft_id": draft.id, "plan": plan}


class GoalAnalysisRefreshBody(BaseModel):
    pass


@router.post("/goals/analysis")
async def goal_analysis(
    body: GoalAnalysisRefreshBody = GoalAnalysisRefreshBody(),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Deep AI analysis of all active objectives — synergies, clusters, cross-goal tasks, insights."""
    import json as _json
    from datetime import date as _date, datetime as _datetime, timedelta as _timedelta
    from bot.database.models import BrainDump

    today = _date.today()
    fourteen_ago = _datetime.combine(today - _timedelta(days=14), _datetime.min.time())
    thirty_ago = _datetime.combine(today - _timedelta(days=30), _datetime.min.time())
    seven_ago = _datetime.combine(today - _timedelta(days=7), _datetime.min.time())

    # Load active objectives with key results and tasks
    obj_res = await session.execute(
        select(Objective)
        .options(selectinload(Objective.key_results), selectinload(Objective.tasks))
        .where(and_(Objective.user_id == user.id, Objective.status == "active"))
        .order_by(Objective.created_at)
    )
    objectives = obj_res.scalars().all()

    if not objectives:
        return {
            "groups": [], "synergies": [], "dependencies": [],
            "cross_objective_tasks": [], "insights": [],
            "clarifying_questions": [],
            "overall_momentum": "stable",
            "motivational_message": "Noch keine aktiven Ziele vorhanden. Erstelle dein erstes Ziel!",
        }

    # Recent brain dumps (last 14 days) for additional context
    bd_res = await session.execute(
        select(BrainDump.raw_input, BrainDump.ai_interpretation)
        .where(and_(
            BrainDump.user_id == user.id,
            BrainDump.created_at >= fourteen_ago,
        ))
        .order_by(BrainDump.created_at.desc())
        .limit(5)
    )
    brain_dumps = [
        (row[1] or row[0])[:300] for row in bd_res.all()
    ]

    # Compute momentum scores per objective
    momentum_by_id: dict[int, dict] = {}
    for obj in objectives:
        done_14d_res = await session.execute(
            select(func.count()).select_from(Task).where(and_(
                Task.objective_id == obj.id, Task.status == "done",
                Task.completed_at >= fourteen_ago,
            ))
        )
        done_7d_res = await session.execute(
            select(func.count()).select_from(Task).where(and_(
                Task.objective_id == obj.id, Task.status == "done",
                Task.completed_at >= seven_ago,
            ))
        )
        last_res = await session.execute(
            select(Task.completed_at).where(and_(
                Task.objective_id == obj.id, Task.status == "done",
                Task.completed_at >= thirty_ago,
            )).order_by(Task.completed_at.desc()).limit(1)
        )
        done_14d = done_14d_res.scalar() or 0
        done_7d = done_7d_res.scalar() or 0
        last_row = last_res.scalar_one_or_none()
        days_since = (today - last_row.date()).days if last_row else 30

        score = min(100, max(0, done_14d * 10 - days_since * 2 + (10 if done_14d > 0 else 0)))
        momentum_label = "hoch" if score >= 60 else "mittel" if score >= 30 else "niedrig"
        momentum_by_id[obj.id] = {"score": score, "label": momentum_label, "done_7d": done_7d}

    portfolio_avg = int(sum(v["score"] for v in momentum_by_id.values()) / len(momentum_by_id)) if momentum_by_id else 0

    # Build rich objectives payload including all task titles
    objs_for_prompt = []
    for o in objectives:
        kr_list = [{
            "title": kr.title,
            "metric_type": kr.metric_type,
            "current": kr.current_value,
            "target": kr.target_value,
            "unit": kr.unit,
            "progress_pct": (
                min(100, int((kr.current_value / kr.target_value) * 100))
                if kr.target_value and kr.target_value > 0 else 0
            ),
        } for kr in o.key_results]

        open_tasks = [t.title for t in o.tasks if t.status not in ("done", "cancelled")][:8]
        done_tasks = [t.title for t in o.tasks if t.status == "done"][:4]

        objs_for_prompt.append({
            "id": o.id,
            "title": o.title,
            "description": o.description or "",
            "category": o.category,
            "target_date": o.target_date.isoformat() if o.target_date else None,
            "key_results": kr_list,
            "open_tasks": open_tasks,
            "recently_done_tasks": done_tasks,
            "momentum_score": momentum_by_id[o.id]["score"],
            "momentum_label": momentum_by_id[o.id]["label"],
            "tasks_done_7d": momentum_by_id[o.id]["done_7d"],
        })

    objectives_json = _json.dumps(objs_for_prompt, ensure_ascii=False, indent=2)
    brain_dump_context = ""
    if brain_dumps:
        brain_dump_context = "\n\nLetzten Brain Dumps des Nutzers (Kontext):\n" + "\n---\n".join(f'"{d}"' for d in brain_dumps)

    n = len(objectives)
    min_synergies = max(1, min(n - 1, 3)) if n >= 2 else 0

    system = """Du bist ein brillanter Life-Coach, Stratege und OKR-Experte.
Deine Aufgabe: Die Ziele eines Menschen tiefgreifend analysieren, verborgene Synergien aufdecken,
kritische Abhängigkeiten erkennen und konkrete Handlungsempfehlungen geben.

WICHTIGSTE REGEL: Du MUSST nach Synergien suchen — auch wenn die Ziele auf den ersten Blick unabhängig wirken.
Frage dich: Welche Gewohnheiten, Fähigkeiten, Zeit oder Energie teilen diese Ziele?
Welche Stärke aus einem Ziel hilft beim anderen? Was kann parallel erledigt werden?

Antworte auf Deutsch. Antworte NUR als valides JSON."""

    prompt = f"""Heute: {today.isoformat()} | Portfolio-Momentum: {portfolio_avg}/100 | Anzahl Ziele: {n}
{brain_dump_context}

=== AKTIVE ZIELE ===
{objectives_json}

=== ANALYSEAUFTRAG ===
Analysiere ALLE {n} Ziele gemeinsam als ein System. Suche aktiv nach:
1. Synergien: Wo stärken sich Ziele gegenseitig? (Mindestens {min_synergies} Synergien wenn {n} Ziele)
2. Clustern: Welche Ziele gehören zum gleichen Lebensbereich?
3. Schlüsselziele: Welches eine Ziel hat den größten Hebel auf die anderen?
4. Risiken: Welche Ziele stagnieren oder gefährden andere?
5. Quick Wins: Was kann HEUTE getan werden, um mehrere Ziele gleichzeitig voranzubringen?

Antworte AUSSCHLIESSLICH als JSON mit exakt dieser Struktur:
{{
  "groups": [
    {{
      "area": "Name des Lebensbereichs",
      "emoji": "🎯",
      "objectives": [<Objective-IDs als Integer-Array>],
      "insight": "Strategische Einschätzung des Bereichs in 1-2 Sätzen",
      "momentum_label": "hoch|mittel|niedrig",
      "key_leverage": "Das eine wichtigste Ziel in diesem Bereich (Objective-ID als Integer)"
    }}
  ],
  "synergies": [
    {{
      "objective_ids": [<int>, <int>],
      "type": "reinforcing|sequential|shared_habit",
      "title": "Prägnanter Synergietitel",
      "description": "Konkret: wie und warum diese Ziele sich gegenseitig verstärken",
      "action_tip": "Ein konkreter Tipp wie man diese Synergie heute nutzt"
    }}
  ],
  "key_objective": {{
    "id": <int>,
    "reason": "Warum dieses Ziel der wichtigste Hebel ist (1-2 Sätze)"
  }},
  "dependencies": [
    {{
      "from_objective_id": <int>,
      "to_objective_id": <int>,
      "description": "Konkrete Abhängigkeit: Ziel X ermöglicht / blockiert Ziel Y weil..."
    }}
  ],
  "cross_objective_tasks": [
    {{
      "title": "Konkreter, actionabler Task-Titel",
      "category": "Kategorie",
      "priority": <1-3>,
      "impacts_objective_ids": [<int>, ...],
      "why": "Wie genau zahlt dieser Task auf mehrere Ziele ein"
    }}
  ],
  "insights": [
    {{
      "type": "warning|opportunity|milestone",
      "title": "Kurzer Titel",
      "description": "Konkreter, handlungsorienterter Hinweis",
      "objective_id": <int oder null>
    }}
  ],
  "clarifying_questions": [
    {{
      "question": "Eine Frage an den Nutzer die die Analyse verbessern würde",
      "why": "Warum diese Info wichtig wäre"
    }}
  ],
  "overall_momentum": "growing|stable|at_risk",
  "motivational_message": "Persönliche, kraftvolle Nachricht (2-3 Sätze, auf die spezifischen Ziele eingehen)"
}}

PFLICHT-REGELN:
- groups: ALLE Objective-IDs müssen in genau einer Gruppe sein
- synergies: MINDESTENS {min_synergies} Synergien (du wirst immer welche finden — Disziplin und Struktur sind fast immer shared_habits)
- key_objective: GENAU 1 Schlüsselziel
- cross_objective_tasks: 3-5 Tasks die WIRKLICH 2+ Ziele betreffen
- insights: 4-6 (mindestens 1 warning, 1 opportunity, 1 milestone)
- clarifying_questions: 1-2 Fragen die die Analyse signifikant verbessern würden (oder [] wenn keine nötig)
- Alle IDs müssen aus der Zielliste stammen: {[o["id"] for o in objs_for_prompt]}"""

    client = _goal_openai_client()
    try:
        resp = await client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
            temperature=0.3,
            response_format={"type": "json_object"},
        )
        analysis = _json.loads(resp.choices[0].message.content)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"KI-Analyse fehlgeschlagen: {exc}") from exc

    # Normalize — ensure all expected keys exist
    analysis.setdefault("clarifying_questions", [])
    analysis.setdefault("key_objective", None)
    analysis.setdefault("synergies", [])
    analysis.setdefault("groups", [])
    analysis.setdefault("cross_objective_tasks", [])
    analysis.setdefault("insights", [])
    analysis.setdefault("dependencies", [])

    return analysis


# ─── Intelligence API ─────────────────────────────────────────────────────────

class DailyContextBody(BaseModel):
    energy: int
    hours_available: float
    focus_area: str
    mood_note: Optional[str] = None


class EveningCheckinBody(BaseModel):
    completed_task_ids: list[int]
    win_of_day: Optional[str] = None
    blocker: Optional[str] = None


@router.get("/intelligence/daily-context")
async def get_daily_context(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Return today's DailyContext for current user, or null if none exists."""
    from datetime import date as _date
    today = _date.today()
    result = await session.execute(
        select(DailyContext).where(
            and_(DailyContext.user_id == user.id, DailyContext.date == today)
        )
    )
    ctx = result.scalar_one_or_none()
    if not ctx:
        return {"context": None}
    return {
        "context": {
            "id": ctx.id,
            "date": ctx.date.isoformat(),
            "energy": ctx.energy,
            "hours_available": ctx.hours_available,
            "focus_area": ctx.focus_area,
            "mood_note": ctx.mood_note,
            "daily_plan": ctx.daily_plan,
        }
    }


@router.post("/intelligence/daily-context")
async def upsert_daily_context(
    body: DailyContextBody,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Upsert today's DailyContext and immediately generate the daily plan."""
    from datetime import date as _date
    today = _date.today()

    result = await session.execute(
        select(DailyContext).where(
            and_(DailyContext.user_id == user.id, DailyContext.date == today)
        )
    )
    ctx = result.scalar_one_or_none()
    if ctx is None:
        ctx = DailyContext(user_id=user.id, date=today)
        session.add(ctx)

    ctx.energy = body.energy
    ctx.hours_available = body.hours_available
    ctx.focus_area = body.focus_area
    ctx.mood_note = body.mood_note
    await session.flush()

    # Generate daily plan immediately after saving context
    plan_result = await _generate_daily_plan_for_user(user, session, ctx)

    ctx.daily_plan = plan_result
    await session.commit()
    await session.refresh(ctx)

    return {
        "context": {
            "id": ctx.id,
            "date": ctx.date.isoformat(),
            "energy": ctx.energy,
            "hours_available": ctx.hours_available,
            "focus_area": ctx.focus_area,
            "mood_note": ctx.mood_note,
            "daily_plan": ctx.daily_plan,
        },
        "daily_plan": plan_result,
    }


async def _generate_daily_plan_for_user(user: User, session: AsyncSession, ctx: Optional[DailyContext]) -> dict:
    """Internal helper: generate a smart daily plan and return it as a dict."""
    import json as _json
    from datetime import date as _date, datetime as _datetime, timedelta as _timedelta

    today = _date.today()

    # Load open tasks with objective/KR links
    task_res = await session.execute(
        select(Task)
        .options(selectinload(Task.objective))
        .where(
            and_(
                Task.user_id == user.id,
                Task.status.in_(["todo", "in_progress"]),
            )
        )
        .order_by(Task.priority.asc().nullslast(), Task.created_at.asc())
        .limit(50)
    )
    tasks = task_res.scalars().all()

    # Determine which objectives had a task completed in the last 7 days
    seven_ago = _datetime.combine(today - _timedelta(days=7), _datetime.min.time())
    stale_obj_ids: set[int] = set()
    if tasks:
        obj_ids_with_tasks = {t.objective_id for t in tasks if t.objective_id}
        for obj_id in obj_ids_with_tasks:
            recent_res = await session.execute(
                select(func.count()).select_from(Task).where(
                    and_(
                        Task.objective_id == obj_id,
                        Task.status == "done",
                        Task.completed_at >= seven_ago,
                    )
                )
            )
            count = recent_res.scalar() or 0
            if count == 0:
                stale_obj_ids.add(obj_id)

    energy = ctx.energy if ctx else 5
    hours_available = ctx.hours_available if ctx else 8.0
    focus_area = ctx.focus_area if ctx else ""

    # Score each task
    scored = []
    for task in tasks:
        base = (6 - (task.priority or 3)) * 20
        deadline_bonus = 0
        if task.due_date:
            days_until = (task.due_date - today).days
            if days_until < 0:
                deadline_bonus = 60
            elif days_until <= 3:
                deadline_bonus = 40
            elif days_until <= 7:
                deadline_bonus = 20
        momentum_risk = 30 if (task.objective_id and task.objective_id in stale_obj_ids) else 0
        energy_match = -20 if (energy <= 4 and (task.priority or 3) >= 3) else 0
        total = base + deadline_bonus + momentum_risk + energy_match
        scored.append((total, task))

    scored.sort(key=lambda x: x[0], reverse=True)
    top_tasks = [t for _, t in scored[:3]]

    # Load KR titles for top tasks
    kr_by_obj: dict[int, list[str]] = {}
    obj_title_by_id: dict[int, str] = {}
    top_obj_ids = {t.objective_id for t in top_tasks if t.objective_id}
    if top_obj_ids:
        kr_res = await session.execute(
            select(KeyResult).where(KeyResult.objective_id.in_(top_obj_ids))
        )
        for kr in kr_res.scalars().all():
            kr_by_obj.setdefault(kr.objective_id, []).append(kr.title)
        obj_res = await session.execute(
            select(Objective).where(Objective.id.in_(top_obj_ids))
        )
        for obj in obj_res.scalars().all():
            obj_title_by_id[obj.id] = obj.title

    tasks_for_prompt = []
    for task in top_tasks:
        obj_title = obj_title_by_id.get(task.objective_id, "") if task.objective_id else ""
        kr_titles = kr_by_obj.get(task.objective_id, []) if task.objective_id else []
        tasks_for_prompt.append(
            f"- [{task.id}] {task.title} (Objective: {obj_title or 'keines'}, KRs: {', '.join(kr_titles[:2]) or 'keine'})"
        )

    tasks_text = "\n".join(tasks_for_prompt) if tasks_for_prompt else "Keine offenen Tasks."

    fallback_plan = {
        "top_tasks": [
            {
                "task_id": t.id,
                "title": t.title,
                "objective_title": obj_title_by_id.get(t.objective_id, "") if t.objective_id else "",
                "kr_title": (kr_by_obj.get(t.objective_id, [""])[0]) if t.objective_id else "",
                "reason": "Höchste Priorität",
                "estimated_minutes": 60,
                "energy_required": "medium",
            }
            for t in top_tasks
        ],
        "focus_block": {
            "suggested_start": "09:00",
            "duration_minutes": 90,
            "description": f"Fokus-Block für {focus_area or 'deine wichtigsten Aufgaben'}",
        },
        "motivational_kickoff": "Mach heute einen wichtigen Schritt vorwärts!",
    }

    try:
        client = _goal_openai_client()
        prompt = (
            f"Nutzer hat heute {energy}/10 Energie, {hours_available} Stunden Zeit. "
            f"Fokus: {focus_area or 'allgemein'}. "
            f"Die 3 priorisierten Tasks sind:\n{tasks_text}\n\n"
            "Generiere JSON mit: {\"top_tasks\": [{\"task_id\": int, \"title\": str, "
            "\"objective_title\": str, \"kr_title\": str, \"reason\": str, "
            "\"estimated_minutes\": int, \"energy_required\": \"low\"|\"medium\"|\"high\"}], "
            "\"focus_block\": {\"suggested_start\": \"HH:MM\", \"duration_minutes\": int, "
            "\"description\": str}, \"motivational_kickoff\": str}"
        )
        resp = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
            response_format={"type": "json_object"},
        )
        return _json.loads(resp.choices[0].message.content)
    except Exception:
        return fallback_plan


@router.post("/intelligence/daily-plan")
async def generate_daily_plan(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Generate a smart daily plan based on today's context and open tasks."""
    from datetime import date as _date, datetime as _datetime

    today = _date.today()
    ctx_res = await session.execute(
        select(DailyContext).where(
            and_(DailyContext.user_id == user.id, DailyContext.date == today)
        )
    )
    ctx = ctx_res.scalar_one_or_none()

    plan = await _generate_daily_plan_for_user(user, session, ctx)

    if ctx is not None:
        ctx.daily_plan = plan
        await session.commit()

    return {
        "daily_plan": plan,
        "generated_at": _datetime.utcnow().isoformat(),
    }


@router.get("/intelligence/streak-risks")
async def get_streak_risks(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Return active objectives with no task completed in the last N days (at-risk streaks)."""
    from datetime import date as _date, datetime as _datetime, timedelta as _timedelta

    today = _date.today()
    fourteen_ago = _datetime.combine(today - _timedelta(days=14), _datetime.min.time())

    obj_res = await session.execute(
        select(Objective)
        .where(and_(Objective.user_id == user.id, Objective.status == "active"))
    )
    objectives = obj_res.scalars().all()

    risks = []
    for obj in objectives:
        # Last completed task within 14 days
        last_res = await session.execute(
            select(Task.completed_at)
            .where(
                and_(
                    Task.objective_id == obj.id,
                    Task.status == "done",
                    Task.completed_at >= fourteen_ago,
                )
            )
            .order_by(Task.completed_at.desc())
            .limit(1)
        )
        last_completed = last_res.scalar_one_or_none()
        if last_completed:
            days_since = (today - last_completed.date()).days
        else:
            days_since = 14

        if days_since < 3:
            continue

        # Count open tasks for this objective
        open_res = await session.execute(
            select(func.count()).select_from(Task).where(
                and_(
                    Task.objective_id == obj.id,
                    Task.status.in_(["todo", "in_progress"]),
                )
            )
        )
        open_task_count = open_res.scalar() or 0

        # Suggested action: first open task title
        first_task_res = await session.execute(
            select(Task.title)
            .where(
                and_(
                    Task.objective_id == obj.id,
                    Task.status.in_(["todo", "in_progress"]),
                )
            )
            .order_by(Task.priority.asc().nullslast(), Task.created_at.asc())
            .limit(1)
        )
        suggested_action = first_task_res.scalar_one_or_none()

        risks.append({
            "objective_id": obj.id,
            "title": obj.title,
            "category": obj.category,
            "days_since": days_since,
            "open_task_count": open_task_count,
            "suggested_action": suggested_action,
        })

    risks.sort(key=lambda x: x["days_since"], reverse=True)
    return {"risks": risks}


@router.post("/intelligence/evening-checkin")
async def post_evening_checkin(
    body: EveningCheckinBody,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Upsert evening check-in: mark tasks done, generate gap analysis."""
    import json as _json
    from datetime import date as _date, datetime as _datetime

    today = _date.today()
    now = _datetime.utcnow()

    # Upsert EveningCheckin
    checkin_res = await session.execute(
        select(EveningCheckin).where(
            and_(EveningCheckin.user_id == user.id, EveningCheckin.date == today)
        )
    )
    checkin = checkin_res.scalar_one_or_none()
    if checkin is None:
        checkin = EveningCheckin(user_id=user.id, date=today)
        session.add(checkin)

    # Mark provided task IDs as done
    tasks_marked = 0
    completed_titles: list[str] = []
    if body.completed_task_ids:
        task_res = await session.execute(
            select(Task).where(
                and_(Task.id.in_(body.completed_task_ids), Task.user_id == user.id)
            )
        )
        for task in task_res.scalars().all():
            if task.status != "done":
                task.status = "done"
                task.completed_at = now
                tasks_marked += 1
            completed_titles.append(task.title)

    tasks_completed = len(body.completed_task_ids)

    # Load today's DailyContext for tasks_planned
    ctx_res = await session.execute(
        select(DailyContext).where(
            and_(DailyContext.user_id == user.id, DailyContext.date == today)
        )
    )
    ctx = ctx_res.scalar_one_or_none()
    tasks_planned = 3  # default if no context
    if ctx and ctx.daily_plan:
        top_tasks = ctx.daily_plan.get("top_tasks", [])
        tasks_planned = len(top_tasks) if top_tasks else 3

    checkin.tasks_planned = tasks_planned
    checkin.tasks_completed = tasks_completed
    checkin.completed_task_ids = body.completed_task_ids
    checkin.win_of_day = body.win_of_day
    checkin.blocker = body.blocker
    await session.flush()

    # Load active objectives for context
    obj_res = await session.execute(
        select(Objective).where(
            and_(Objective.user_id == user.id, Objective.status == "active")
        )
    )
    active_objectives = [o.title for o in obj_res.scalars().all()]

    completion_rate = int((tasks_completed / tasks_planned) * 100) if tasks_planned > 0 else 0

    fallback_gap = {
        "completion_rate_pct": completion_rate,
        "gap_summary": f"{tasks_completed} von {tasks_planned} Tasks erledigt.",
        "positive_note": body.win_of_day or "Guter Fortschritt heute!",
        "tomorrow_focus": {"objective_title": active_objectives[0] if active_objectives else "", "suggested_task_title": ""},
        "pattern_note": "",
    }

    try:
        client = _goal_openai_client()
        prompt = (
            f"Heute geplant: {tasks_planned} Tasks, erledigt: {tasks_completed}. "
            f"Win des Tages: {body.win_of_day or 'nicht angegeben'}. "
            f"Blocker: {body.blocker or 'keiner'}. "
            f"Erledigte Tasks: {', '.join(completed_titles) or 'keine'}. "
            f"Aktive Ziele: {', '.join(active_objectives[:5]) or 'keine'}. "
            "Generiere gap_analysis JSON: {\"completion_rate_pct\": int, \"gap_summary\": str, "
            "\"positive_note\": str, \"tomorrow_focus\": {\"objective_title\": str, "
            "\"suggested_task_title\": str}, \"pattern_note\": str}"
        )
        resp = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
            response_format={"type": "json_object"},
        )
        gap_analysis = _json.loads(resp.choices[0].message.content)
    except Exception:
        gap_analysis = fallback_gap

    checkin.gap_analysis = gap_analysis
    await session.commit()
    await session.refresh(checkin)

    return {
        "checkin": {
            "id": checkin.id,
            "date": checkin.date.isoformat(),
            "tasks_planned": checkin.tasks_planned,
            "tasks_completed": checkin.tasks_completed,
            "completed_task_ids": checkin.completed_task_ids,
            "win_of_day": checkin.win_of_day,
            "blocker": checkin.blocker,
            "gap_analysis": checkin.gap_analysis,
        },
        "gap_analysis": gap_analysis,
        "tasks_marked_done": tasks_marked,
    }


@router.get("/intelligence/evening-checkin")
async def get_evening_checkin(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Return today's EveningCheckin for current user, or null."""
    from datetime import date as _date
    today = _date.today()
    result = await session.execute(
        select(EveningCheckin).where(
            and_(EveningCheckin.user_id == user.id, EveningCheckin.date == today)
        )
    )
    checkin = result.scalar_one_or_none()
    if not checkin:
        return {"checkin": None}
    return {
        "checkin": {
            "id": checkin.id,
            "date": checkin.date.isoformat(),
            "tasks_planned": checkin.tasks_planned,
            "tasks_completed": checkin.tasks_completed,
            "completed_task_ids": checkin.completed_task_ids,
            "win_of_day": checkin.win_of_day,
            "blocker": checkin.blocker,
            "gap_analysis": checkin.gap_analysis,
        }
    }


@router.post("/intelligence/weekly-plan")
async def generate_weekly_plan(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Generate next week's task plan from lagging KRs. Result is not persisted."""
    import json as _json
    from datetime import datetime as _datetime

    # Load active objectives with KRs
    obj_res = await session.execute(
        select(Objective)
        .options(selectinload(Objective.key_results))
        .where(and_(Objective.user_id == user.id, Objective.status == "active"))
        .order_by(Objective.created_at)
    )
    objectives = obj_res.scalars().all()

    if not objectives:
        return {
            "weekly_plan": {
                "week_theme": "Erste Ziele anlegen",
                "daily_focus": [],
                "key_priorities": [],
                "weekly_commitment": "Starte diese Woche mit dem Anlegen deiner ersten Ziele!",
            },
            "generated_at": _datetime.utcnow().isoformat(),
        }

    # Compute progress_pct for each KR and find lagging ones
    lagging_krs = []
    for obj in objectives:
        for kr in obj.key_results:
            target = kr.target_value or 0
            current = kr.current_value or 0
            if target > 0:
                progress_pct = min(100, int((current / target) * 100))
            else:
                progress_pct = 0
            lagging_krs.append({
                "kr_title": kr.title,
                "objective_title": obj.title,
                "progress_pct": progress_pct,
                "current": current,
                "target": target,
                "unit": kr.unit or "",
            })

    lagging_krs.sort(key=lambda x: x["progress_pct"])
    top_lagging = lagging_krs[:5]

    lagging_text = "\n".join(
        f"- {item['kr_title']} (Objective: {item['objective_title']}, "
        f"Fortschritt: {item['progress_pct']}%, {item['current']}/{item['target']} {item['unit']})"
        for item in top_lagging
    )

    fallback_plan = {
        "week_theme": "Fokus auf rückständige Ziele",
        "daily_focus": [
            {"day": kr["objective_title"][:20], "objective_title": kr["objective_title"], "task_title": kr["kr_title"], "estimated_minutes": 60}
            for kr in top_lagging[:5]
        ],
        "key_priorities": [
            {"kr_title": kr["kr_title"], "why_urgent": f"Nur {kr['progress_pct']}% erreicht", "suggested_tasks": [kr["kr_title"]]}
            for kr in top_lagging
        ],
        "weekly_commitment": "Diese Woche konzentriere ich mich auf die rückständigsten Key Results.",
    }

    try:
        client = _goal_openai_client()
        prompt = (
            f"Basierend auf diesen KRs die am weitesten hinter dem Ziel sind:\n{lagging_text}\n\n"
            "Generiere einen Wochenplan als JSON: {\"week_theme\": str, "
            "\"daily_focus\": [{\"day\": \"Montag\"|\"Dienstag\"|\"Mittwoch\"|\"Donnerstag\"|\"Freitag\", "
            "\"objective_title\": str, \"task_title\": str, \"estimated_minutes\": int}], "
            "\"key_priorities\": [{\"kr_title\": str, \"why_urgent\": str, \"suggested_tasks\": [str]}], "
            "\"weekly_commitment\": str}"
        )
        resp = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
            response_format={"type": "json_object"},
        )
        weekly_plan = _json.loads(resp.choices[0].message.content)
    except Exception:
        weekly_plan = fallback_plan

    return {
        "weekly_plan": weekly_plan,
        "generated_at": _datetime.utcnow().isoformat(),
    }


@router.get("/intelligence/patterns")
async def get_productivity_patterns(
    days: int = Query(28, ge=7, le=90),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Sprint 4: Compute productivity patterns for the past N days."""
    from bot.core.pattern_memory import compute_productivity_patterns
    patterns = await compute_productivity_patterns(session, user, days=days)
    return patterns


@router.get("/intelligence/correlations")
async def get_correlations(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Return health/behavior correlation insights."""
    from bot.core.correlation_engine import run_correlation_analysis
    insights = await run_correlation_analysis(session, user.id)
    return {"correlations": insights, "analysis_days": 30}


@router.post("/intelligence/correlations/refresh")
async def refresh_correlations(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Re-run correlation analysis and store as UserInsight rows."""
    from bot.core.correlation_engine import run_correlation_analysis
    insights = await run_correlation_analysis(session, user.id)

    # Store as UserInsight rows
    from bot.database.models import UserInsight
    # Deactivate old correlation insights
    old = await session.execute(
        select(UserInsight).where(and_(
            UserInsight.user_id == user.id,
            UserInsight.insight_type == "correlation",
            UserInsight.source == "auto_detected",
        ))
    )
    for old_ins in old.scalars().all():
        old_ins.active = False

    for ins in insights:
        session.add(UserInsight(
            user_id=user.id,
            insight_type="correlation",
            title=ins["title"],
            description=ins["description"],
            source="auto_detected",
            active=True,
            data_basis=ins.get("data"),
        ))
    await session.commit()
    return {"ok": True, "correlations": insights, "count": len(insights)}


@router.get("/intelligence/day-schedule")
async def get_day_schedule(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Get today's auto-scheduled time blocks."""
    from datetime import date as _date, datetime as _dt, time as _time
    today = _date.today()
    day_start = _dt.combine(today, _time(0, 0))
    day_end = _dt.combine(today, _time(23, 59))

    res = await session.execute(
        select(CalendarEvent).where(and_(
            CalendarEvent.user_id == user.id,
            CalendarEvent.start_time >= day_start,
            CalendarEvent.start_time <= day_end,
            CalendarEvent.event_type == "work_block",
        )).order_by(CalendarEvent.start_time)
    )
    blocks = res.scalars().all()

    return {
        "date": today.isoformat(),
        "blocks": [
            {
                "id": b.id,
                "title": b.title,
                "start_time": b.start_time.strftime("%H:%M"),
                "end_time": b.end_time.strftime("%H:%M") if b.end_time else None,
                "task_id": b.linked_task_id,
                "routine_id": b.linked_routine_id,
            }
            for b in blocks
        ],
        "count": len(blocks),
    }


@router.post("/intelligence/day-schedule/generate")
async def trigger_day_schedule(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Manually trigger day schedule generation for today."""
    from bot.core.day_scheduler import generate_day_schedule
    schedule, daily_focus = await generate_day_schedule(session, user)
    await session.commit()
    return {
        "generated": len(schedule),
        "daily_focus": daily_focus,
        "schedule": schedule,
    }


@router.get("/intelligence/next-action")
async def get_next_action_intelligence(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Sprint 5: Single best next action with context (dashboard use)."""
    from bot.core.next_action import get_next_action
    action = await get_next_action(session, user)
    if not action:
        return {"action": None, "message": "Keine offenen Tasks"}
    return {"action": action}


# ─── iCal / Google Calendar Sync ─────────────────────────────────────────────

class SetIcalBody(BaseModel):
    ical_url: Optional[str] = None


@router.get("/settings/ical")
async def get_ical_status(
    user: User = Depends(get_current_user),
) -> dict:
    """Get current iCal sync status."""
    return {
        "ical_url": user.ical_url,
        "configured": bool(user.ical_url),
    }


@router.put("/settings/ical")
async def set_ical_url(
    body: SetIcalBody,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Save Google Calendar iCal URL and trigger immediate sync."""
    user.ical_url = body.ical_url.strip() if body.ical_url else None
    await session.flush()

    if user.ical_url:
        try:
            from bot.jobs.ical_sync import sync_ical_for_user
            count = await sync_ical_for_user(session, user)
            return {"ok": True, "synced": count, "message": f"{count} Events importiert ✓"}
        except Exception as e:
            return {"ok": True, "synced": 0, "message": f"URL gespeichert, Sync fehlgeschlagen: {e}"}

    return {"ok": True, "synced": 0, "message": "iCal URL entfernt"}

# ─── Finance Routes ───────────────────────────────────────────────────────────

@router.get("/finance/summary")
async def get_finance_summary(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Monthly financial summary: income, expenses by category, budget status."""
    from bot.core.finance import get_financial_summary
    return await get_financial_summary(session, user.id)


@router.get("/finance/transactions")
async def list_transactions(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    month: Optional[int] = None,
    year: Optional[int] = None,
    type: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = 50,
):
    """List financial transactions with optional filters."""
    from bot.database.models import FinancialTransaction
    from sqlalchemy import extract
    today = date.today()
    q = select(FinancialTransaction).where(FinancialTransaction.user_id == user.id)
    if month:
        q = q.where(extract("month", FinancialTransaction.transaction_date) == month)
    if year:
        q = q.where(extract("year", FinancialTransaction.transaction_date) == year)
    else:
        q = q.where(extract("year", FinancialTransaction.transaction_date) == today.year)
    if type:
        q = q.where(FinancialTransaction.type == type)
    if category:
        q = q.where(FinancialTransaction.category == category)
    q = q.order_by(FinancialTransaction.transaction_date.desc()).limit(limit)
    result = await session.execute(q)
    txs = result.scalars().all()
    return [
        {
            "id": t.id, "amount": t.amount, "type": t.type, "category": t.category,
            "description": t.description, "date": str(t.transaction_date),
            "is_recurring": t.is_recurring,
        }
        for t in txs
    ]


@router.post("/finance/transactions")
async def create_transaction(
    body: dict,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Manually create a financial transaction."""
    from bot.core.finance import log_expense, log_income
    tx_type = body.get("type", "expense")
    tx_date = None
    if body.get("date"):
        try:
            tx_date = date.fromisoformat(body["date"])
        except ValueError:
            pass
    if tx_type == "income":
        result = await log_income(session, user.id, float(body["amount"]), body.get("source", ""), tx_date)
    else:
        result = await log_expense(
            session, user.id, float(body["amount"]),
            body.get("category", "sonstiges"), body.get("description", ""),
            tx_date, body.get("is_recurring", False),
        )
    await session.commit()
    return result


@router.delete("/finance/transactions/{tx_id}")
async def delete_transaction(
    tx_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Delete a financial transaction."""
    from bot.database.models import FinancialTransaction
    result = await session.execute(
        select(FinancialTransaction).where(
            FinancialTransaction.id == tx_id,
            FinancialTransaction.user_id == user.id,
        )
    )
    tx = result.scalar_one_or_none()
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")
    await session.delete(tx)
    await session.commit()
    return {"deleted": True}


@router.get("/finance/budgets")
async def list_budgets(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """List all budget limits."""
    from bot.database.models import Budget
    result = await session.execute(select(Budget).where(Budget.user_id == user.id))
    budgets = result.scalars().all()
    return [{"id": b.id, "category": b.category, "monthly_limit": b.monthly_limit} for b in budgets]


@router.put("/finance/budgets/{category}")
async def upsert_budget(
    category: str,
    body: dict,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Create or update a monthly budget."""
    from bot.core.finance import set_budget
    result = await set_budget(session, user.id, category, float(body["monthly_limit"]))
    await session.commit()
    return result


# ─── Health Sync Routes ───────────────────────────────────────────────────────

@router.post("/health/sync")
async def sync_health_data(
    body: dict,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Universal health sync endpoint.

    Accepts JSON with any combination of:
    {
        "sleep_hours": 7.5,
        "sleep_quality": 8,
        "steps": 9200,
        "hrv": 52,
        "weight_kg": 78.5,
        "calories": 2100,
        "active_minutes": 45,
        "resting_heart_rate": 58,
        "spo2": 98.5,
        "stress_score": 25,
        "metric_date": "2026-03-17"  // optional, default today
    }

    Can be called from iOS Shortcuts, Huawei Health automation, or any HTTP client.
    """
    from bot.core.health_sync import sync_health_metrics
    result = await sync_health_metrics(session, user, body, source=body.get("source", "api"))
    await session.commit()
    return {"ok": True, **result}


@router.post("/health/import/huawei")
async def import_huawei_export(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    request: None = None,
):
    """
    Import Huawei Health ZIP export file.

    Send raw ZIP bytes as request body.
    Parses sleep, steps, HRV from Huawei Health CSV files inside the ZIP.
    """
    from fastapi import Request as FastAPIRequest
    from bot.core.health_sync import parse_huawei_export, sync_health_metrics
    # We need the raw body — use a workaround via dependency
    raise HTTPException(status_code=501, detail="Use the /health/import/huawei-upload endpoint")


@router.post("/health/import/huawei-upload")
async def import_huawei_upload(
    request_obj: None = None,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Placeholder — actual implementation reads raw body via Request."""
    raise HTTPException(status_code=501, detail="Send ZIP as raw body to /health/import/huawei-raw")


from fastapi import Request as _Request


@router.post("/health/import/huawei-raw")
async def import_huawei_raw(
    request: _Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Import Huawei Health ZIP export file.

    Send raw ZIP bytes as request body with Content-Type: application/zip.
    Parses sleep, steps, HRV from Huawei Health CSV files inside the ZIP.
    """
    from bot.core.health_sync import parse_huawei_export, sync_health_metrics
    body = await request.body()
    if not body:
        raise HTTPException(status_code=400, detail="No file data received")

    daily_metrics = await parse_huawei_export(body)

    if not daily_metrics:
        raise HTTPException(
            status_code=400,
            detail="Could not parse Huawei Health export. Ensure you export from Huawei Health app as ZIP.",
        )

    imported = 0
    for day_data in daily_metrics:
        result = await sync_health_metrics(session, user, day_data, source="huawei_export")
        if result.get("stored"):
            imported += 1

    await session.commit()
    return {
        "ok": True,
        "days_imported": imported,
        "total_days_in_file": len(daily_metrics),
    }


@router.post("/health/import/apple-health")
async def import_apple_health(
    request: _Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Import Apple Health export ZIP (contains export.xml).

    Send raw ZIP bytes as request body.
    """
    from bot.core.health_sync import parse_apple_health_export, sync_health_metrics
    body = await request.body()
    if not body:
        raise HTTPException(status_code=400, detail="No file data received")

    daily_metrics = parse_apple_health_export(body)

    if not daily_metrics:
        raise HTTPException(
            status_code=400,
            detail="Could not parse Apple Health export. Ensure you export from Apple Health as ZIP.",
        )

    imported = 0
    kr_updates = []
    for day_data in daily_metrics:
        result = await sync_health_metrics(session, user, day_data, source="apple_health")
        if result.get("stored"):
            imported += 1
        kr_updates.extend(result.get("kr_updates", []))

    await session.commit()
    return {
        "ok": True,
        "days_imported": imported,
        "total_days_in_file": len(daily_metrics),
        "kr_updates": kr_updates,
    }


@router.post("/health/import/csv")
async def import_health_csv(
    request: _Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Import health data from CSV file.

    Supports two formats:
    - Wide: date,steps,sleep_hours,weight_kg,...
    - Long: date,metric,value
    """
    from bot.core.health_sync import parse_generic_csv, sync_health_metrics
    body = await request.body()
    if not body:
        raise HTTPException(status_code=400, detail="No file data received")

    content = body.decode("utf-8", errors="ignore")
    daily_metrics = parse_generic_csv(content)

    if not daily_metrics:
        raise HTTPException(
            status_code=400,
            detail="Could not parse CSV. Expected columns: date + metric columns (steps, sleep_hours, etc.) or date/metric/value format.",
        )

    imported = 0
    kr_updates = []
    for day_data in daily_metrics:
        result = await sync_health_metrics(session, user, day_data, source="csv_import")
        if result.get("stored"):
            imported += 1
        kr_updates.extend(result.get("kr_updates", []))

    await session.commit()
    return {
        "ok": True,
        "days_imported": imported,
        "total_days_in_file": len(daily_metrics),
        "kr_updates": kr_updates,
    }


@router.post("/health/import/quick")
async def import_health_quick(
    request: _Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Quick health data import — simple JSON POST for iOS Shortcuts.

    Body: {"steps": 8500, "sleep_hours": 7.2, "weight_kg": 75.5, ...}
    All fields optional. See sync_health_metrics for full list.
    """
    from bot.core.health_sync import sync_health_metrics
    body = await request.json()
    if not body or not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="Expected JSON object with health metrics")

    result = await sync_health_metrics(session, user, body, source="ios_shortcut")
    await session.commit()
    return {"ok": True, **result}


@router.get("/health/metrics")
async def get_health_metrics(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    days: int = 30,
):
    """Return health metrics history (sleep, steps, HRV, weight) for the last N days."""
    since = datetime.utcnow() - timedelta(days=days)

    result = await session.execute(
        select(Log).where(and_(
            Log.user_id == user.id,
            Log.log_type.in_(["sleep", "steps", "hrv", "weight", "health_metrics"]),
            Log.logged_at >= since,
        )).order_by(Log.logged_at.desc())
    )
    logs = result.scalars().all()

    metrics = []
    for log in logs:
        entry = {
            "id": log.id,
            "type": log.log_type,
            "date": log.logged_at.strftime("%Y-%m-%d"),
            **(log.data or {}),
        }
        metrics.append(entry)

    return {"metrics": metrics, "days": days}


@router.get("/health/shortcut-setup")
async def get_shortcut_setup(
    request: _Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Return iOS Shortcut setup instructions and the endpoint URL/token.
    The iOS Shortcut should:
    1. Read Health data (sleep, steps, HRV) from Apple Health
    2. POST to this API with the user's token
    """
    base_url = str(request.base_url).rstrip("/")
    token = user.api_token or ""

    shortcut_payload_example = {
        "sleep_hours": "{{Health: Sleep Analysis (hours)}}",
        "steps": "{{Health: Step Count}}",
        "hrv": "{{Health: Heart Rate Variability (ms)}}",
        "metric_date": "{{Current Date YYYY-MM-DD}}",
    }

    return {
        "endpoint": f"{base_url}/api/health/sync",
        "method": "POST",
        "headers": {"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        "payload_example": shortcut_payload_example,
        "instructions": [
            "1. Öffne die Kurzbefehle-App auf deinem iPhone",
            "2. Erstelle einen neuen Kurzbefehl",
            "3. Füge 'Gesundheit: Schlafanalyse abrufen' hinzu",
            "4. Füge 'Gesundheit: Schritte abrufen' hinzu",
            "5. Füge 'URL-Inhalt abrufen' hinzu mit POST, URL oben, Bearer Token im Header",
            "6. Stelle den Kurzbefehl auf tägliche Ausführung (07:00) ein",
            "Für Huawei Honor Watch: Stelle sicher dass Huawei Health → Apple Health Sync aktiviert ist",
        ],
        "huawei_instructions": [
            "1. Öffne die Huawei Health App",
            "2. Gehe zu 'Ich' → 'Einstellungen' → 'Datenverwaltung'",
            "3. Tippe auf 'Daten exportieren' → ZIP herunterladen",
            "4. Sende die ZIP-Datei an: POST /api/health/import/huawei-raw",
            "   mit deinem API-Token im Authorization-Header",
            "Oder: Aktiviere 'Apple Health' Sync in Huawei Health für automatischen täglichen Sync",
        ],
    }


# ─── Feature 5: Automation Rules ─────────────────────────────────────────────

class AutomationRuleBody(BaseModel):
    title: str
    trigger_type: str
    trigger_conditions: Optional[dict] = None
    action_type: str
    action_params: Optional[dict] = None
    cooldown_hours: int = 24
    is_active: bool = True


class AutomationRuleUpdateBody(BaseModel):
    title: Optional[str] = None
    trigger_type: Optional[str] = None
    trigger_conditions: Optional[dict] = None
    action_type: Optional[str] = None
    action_params: Optional[dict] = None
    cooldown_hours: Optional[int] = None
    is_active: Optional[bool] = None


@router.get("/automation/rules")
async def list_automation_rules(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[dict]:
    result = await session.execute(
        select(AutomationRule)
        .where(AutomationRule.user_id == user.id)
        .order_by(AutomationRule.created_at.desc())
    )
    rules = result.scalars().all()
    return [
        {
            "id": r.id,
            "title": r.title,
            "is_active": r.is_active,
            "trigger_type": r.trigger_type,
            "trigger_conditions": r.trigger_conditions,
            "action_type": r.action_type,
            "action_params": r.action_params,
            "cooldown_hours": r.cooldown_hours,
            "last_triggered_at": r.last_triggered_at.isoformat() if r.last_triggered_at else None,
            "trigger_count": r.trigger_count,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rules
    ]


@router.post("/automation/rules")
async def create_automation_rule(
    body: AutomationRuleBody,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    rule = AutomationRule(
        user_id=user.id,
        title=body.title,
        trigger_type=body.trigger_type,
        trigger_conditions=body.trigger_conditions,
        action_type=body.action_type,
        action_params=body.action_params,
        cooldown_hours=body.cooldown_hours,
        is_active=body.is_active,
    )
    session.add(rule)
    await session.flush()
    return {"ok": True, "id": rule.id}


@router.put("/automation/rules/{rule_id}")
async def update_automation_rule(
    rule_id: int,
    body: AutomationRuleUpdateBody,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    result = await session.execute(
        select(AutomationRule).where(
            and_(AutomationRule.id == rule_id, AutomationRule.user_id == user.id)
        )
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    if body.title is not None:
        rule.title = body.title
    if body.trigger_type is not None:
        rule.trigger_type = body.trigger_type
    if body.trigger_conditions is not None:
        rule.trigger_conditions = body.trigger_conditions
    if body.action_type is not None:
        rule.action_type = body.action_type
    if body.action_params is not None:
        rule.action_params = body.action_params
    if body.cooldown_hours is not None:
        rule.cooldown_hours = body.cooldown_hours
    if body.is_active is not None:
        rule.is_active = body.is_active
    await session.flush()
    return {"ok": True}


@router.delete("/automation/rules/{rule_id}")
async def delete_automation_rule(
    rule_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    result = await session.execute(
        select(AutomationRule).where(
            and_(AutomationRule.id == rule_id, AutomationRule.user_id == user.id)
        )
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    await session.delete(rule)
    await session.flush()
    return {"ok": True}


@router.post("/automation/rules/{rule_id}/toggle")
async def toggle_automation_rule(
    rule_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    result = await session.execute(
        select(AutomationRule).where(
            and_(AutomationRule.id == rule_id, AutomationRule.user_id == user.id)
        )
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    rule.is_active = not rule.is_active
    await session.flush()
    return {"ok": True, "is_active": rule.is_active}


@router.get("/automation/templates")
async def get_automation_templates() -> list[dict]:
    from bot.core.rule_engine import get_rule_templates
    return await get_rule_templates()


@router.post("/automation/rules/{rule_id}/trigger")
async def trigger_automation_rule_manually(
    rule_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    result = await session.execute(
        select(AutomationRule).where(
            and_(AutomationRule.id == rule_id, AutomationRule.user_id == user.id)
        )
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    from bot.core.rule_engine import execute_rule
    # Bypass cooldown for manual trigger
    original_last = rule.last_triggered_at
    rule.last_triggered_at = None
    try:
        msg = await execute_rule(session, user, rule, {"manual": True})
        rule.last_triggered_at = original_last
        rule.trigger_count = (rule.trigger_count or 0) + 1
        await session.flush()
        return {"ok": True, "result": msg}
    except Exception as e:
        rule.last_triggered_at = original_last
        raise HTTPException(status_code=500, detail=str(e))


# ─── Feature 6: Quarterly Reviews ────────────────────────────────────────────

class GenerateQuarterlyBody(BaseModel):
    year: Optional[int] = None
    quarter: Optional[int] = None


@router.get("/quarterly-reviews")
async def list_quarterly_reviews(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[dict]:
    result = await session.execute(
        select(QuarterlyReview)
        .where(QuarterlyReview.user_id == user.id)
        .order_by(QuarterlyReview.year.desc(), QuarterlyReview.quarter.desc())
    )
    reviews = result.scalars().all()
    return [
        {
            "id": r.id,
            "year": r.year,
            "quarter": r.quarter,
            "quarter_label": r.quarter_label,
            "life_score": r.life_score,
            "status": r.status,
            "generated_at": r.generated_at.isoformat() if r.generated_at else None,
            "objectives_count": len(r.objectives_data) if r.objectives_data else 0,
        }
        for r in reviews
    ]


@router.get("/quarterly-reviews/latest")
async def get_latest_quarterly_review(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    result = await session.execute(
        select(QuarterlyReview)
        .where(QuarterlyReview.user_id == user.id)
        .order_by(QuarterlyReview.generated_at.desc())
        .limit(1)
    )
    review = result.scalar_one_or_none()
    if not review:
        raise HTTPException(status_code=404, detail="No quarterly reviews found")
    return {
        "id": review.id,
        "year": review.year,
        "quarter": review.quarter,
        "quarter_label": review.quarter_label,
        "life_score": review.life_score,
        "objectives_data": review.objectives_data,
        "ai_analysis": review.ai_analysis,
        "highlights": review.highlights,
        "challenges": review.challenges,
        "status": review.status,
        "generated_at": review.generated_at.isoformat() if review.generated_at else None,
    }


@router.post("/quarterly-reviews/generate")
async def generate_quarterly_review_endpoint(
    body: GenerateQuarterlyBody,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    from bot.core.quarterly_review import generate_quarterly_review
    review = await generate_quarterly_review(
        session, user.id, year=body.year, quarter=body.quarter
    )
    return {
        "id": review.id,
        "year": review.year,
        "quarter": review.quarter,
        "quarter_label": review.quarter_label,
        "life_score": review.life_score,
        "objectives_data": review.objectives_data,
        "ai_analysis": review.ai_analysis,
        "highlights": review.highlights,
        "challenges": review.challenges,
        "status": review.status,
        "generated_at": review.generated_at.isoformat() if review.generated_at else None,
    }


@router.get("/quarterly-reviews/{review_id}")
async def get_quarterly_review(
    review_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    result = await session.execute(
        select(QuarterlyReview).where(
            and_(QuarterlyReview.id == review_id, QuarterlyReview.user_id == user.id)
        )
    )
    review = result.scalar_one_or_none()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    return {
        "id": review.id,
        "year": review.year,
        "quarter": review.quarter,
        "quarter_label": review.quarter_label,
        "life_score": review.life_score,
        "objectives_data": review.objectives_data,
        "ai_analysis": review.ai_analysis,
        "highlights": review.highlights,
        "challenges": review.challenges,
        "status": review.status,
        "generated_at": review.generated_at.isoformat() if review.generated_at else None,
    }


# ─── Feature 8: Relationship Engine ──────────────────────────────────────────

class ContactBody(BaseModel):
    name: str
    nickname: Optional[str] = None
    relationship_type: str = "friend"
    contact_frequency_days: int = 30
    phone: Optional[str] = None
    email: Optional[str] = None
    notes: Optional[str] = None
    birthday: Optional[str] = None  # ISO date string


class ContactUpdateBody(BaseModel):
    name: Optional[str] = None
    nickname: Optional[str] = None
    relationship_type: Optional[str] = None
    contact_frequency_days: Optional[int] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    notes: Optional[str] = None
    birthday: Optional[str] = None


class InteractionBody(BaseModel):
    interaction_type: str
    notes: Optional[str] = None
    quality_score: Optional[int] = None


class CommitmentBody(BaseModel):
    description: str
    contact_id: Optional[int] = None
    due_date: Optional[str] = None  # ISO date string


class CommitmentUpdateBody(BaseModel):
    description: Optional[str] = None
    contact_id: Optional[int] = None
    due_date: Optional[str] = None
    status: Optional[str] = None


@router.get("/contacts")
async def list_contacts(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[dict]:
    from sqlalchemy.orm import selectinload as _sil
    now = datetime.utcnow()

    result = await session.execute(
        select(Contact)
        .where(and_(Contact.user_id == user.id, Contact.is_active == True))  # noqa: E712
        .order_by(Contact.name)
    )
    contacts = result.scalars().all()

    out = []
    for c in contacts:
        if c.last_contacted_at:
            days_since = (now - c.last_contacted_at).days
            overdue_days = days_since - c.contact_frequency_days
        else:
            days_since = None
            overdue_days = None

        out.append({
            "id": c.id,
            "name": c.name,
            "nickname": c.nickname,
            "relationship_type": c.relationship_type,
            "contact_frequency_days": c.contact_frequency_days,
            "last_contacted_at": c.last_contacted_at.isoformat() if c.last_contacted_at else None,
            "days_since_contact": days_since,
            "overdue_days": overdue_days,
            "is_overdue": (overdue_days is not None and overdue_days > 0) or (c.last_contacted_at is None),
            "phone": c.phone,
            "email": c.email,
            "notes": c.notes,
            "birthday": c.birthday.isoformat() if c.birthday else None,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        })
    return out


@router.post("/contacts")
async def create_contact(
    body: ContactBody,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    from datetime import date as _date
    birthday = None
    if body.birthday:
        try:
            birthday = _date.fromisoformat(body.birthday)
        except ValueError:
            pass

    contact = Contact(
        user_id=user.id,
        name=body.name.strip(),
        nickname=body.nickname,
        relationship_type=body.relationship_type,
        contact_frequency_days=body.contact_frequency_days,
        phone=body.phone,
        email=body.email,
        notes=body.notes,
        birthday=birthday,
    )
    session.add(contact)
    await session.flush()
    return {"ok": True, "id": contact.id}


@router.put("/contacts/{contact_id}")
async def update_contact(
    contact_id: int,
    body: ContactUpdateBody,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    from datetime import date as _date
    result = await session.execute(
        select(Contact).where(and_(Contact.id == contact_id, Contact.user_id == user.id))
    )
    contact = result.scalar_one_or_none()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    if body.name is not None:
        contact.name = body.name.strip()
    if body.nickname is not None:
        contact.nickname = body.nickname
    if body.relationship_type is not None:
        contact.relationship_type = body.relationship_type
    if body.contact_frequency_days is not None:
        contact.contact_frequency_days = body.contact_frequency_days
    if body.phone is not None:
        contact.phone = body.phone
    if body.email is not None:
        contact.email = body.email
    if body.notes is not None:
        contact.notes = body.notes
    if body.birthday is not None:
        try:
            contact.birthday = _date.fromisoformat(body.birthday)
        except ValueError:
            pass
    await session.flush()
    return {"ok": True}


@router.delete("/contacts/{contact_id}")
async def delete_contact(
    contact_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    result = await session.execute(
        select(Contact).where(and_(Contact.id == contact_id, Contact.user_id == user.id))
    )
    contact = result.scalar_one_or_none()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    contact.is_active = False
    await session.flush()
    return {"ok": True}


@router.post("/contacts/{contact_id}/interaction")
async def log_contact_interaction(
    contact_id: int,
    body: InteractionBody,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    # Verify contact ownership
    result = await session.execute(
        select(Contact).where(and_(Contact.id == contact_id, Contact.user_id == user.id))
    )
    contact = result.scalar_one_or_none()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    from bot.core.relationships import log_interaction
    interaction = await log_interaction(
        session, user.id, contact_id,
        body.interaction_type,
        notes=body.notes or "",
        quality_score=body.quality_score,
    )
    return {"ok": True, "id": interaction.id}


@router.get("/contacts/{contact_id}/interactions")
async def list_contact_interactions(
    contact_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[dict]:
    # Verify ownership
    result = await session.execute(
        select(Contact).where(and_(Contact.id == contact_id, Contact.user_id == user.id))
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Contact not found")

    result2 = await session.execute(
        select(Interaction)
        .where(and_(Interaction.contact_id == contact_id, Interaction.user_id == user.id))
        .order_by(Interaction.interacted_at.desc())
        .limit(50)
    )
    interactions = result2.scalars().all()
    return [
        {
            "id": i.id,
            "interaction_type": i.interaction_type,
            "quality_score": i.quality_score,
            "notes": i.notes,
            "interacted_at": i.interacted_at.isoformat() if i.interacted_at else None,
        }
        for i in interactions
    ]


@router.get("/commitments")
async def list_commitments(
    status: Optional[str] = Query(None),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[dict]:
    from sqlalchemy.orm import selectinload as _sil

    conditions = [Commitment.user_id == user.id]
    if status:
        conditions.append(Commitment.status == status)

    result = await session.execute(
        select(Commitment)
        .options(_sil(Commitment.contact))
        .where(and_(*conditions))
        .order_by(Commitment.due_date.asc().nulls_last())
    )
    commitments = result.scalars().all()
    return [
        {
            "id": c.id,
            "description": c.description,
            "contact_id": c.contact_id,
            "contact_name": c.contact.name if c.contact else None,
            "due_date": c.due_date.isoformat() if c.due_date else None,
            "status": c.status,
            "reminder_at": c.reminder_at.isoformat() if c.reminder_at else None,
            "completed_at": c.completed_at.isoformat() if c.completed_at else None,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c in commitments
    ]


@router.post("/commitments")
async def create_commitment(
    body: CommitmentBody,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    from datetime import date as _date
    from bot.core.relationships import add_commitment

    due = None
    if body.due_date:
        try:
            due = _date.fromisoformat(body.due_date)
        except ValueError:
            pass

    commitment = await add_commitment(
        session, user.id, body.description,
        contact_id=body.contact_id,
        due_date=due,
    )
    return {"ok": True, "id": commitment.id}


@router.put("/commitments/{commitment_id}")
async def update_commitment(
    commitment_id: int,
    body: CommitmentUpdateBody,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    from datetime import date as _date

    result = await session.execute(
        select(Commitment).where(
            and_(Commitment.id == commitment_id, Commitment.user_id == user.id)
        )
    )
    commitment = result.scalar_one_or_none()
    if not commitment:
        raise HTTPException(status_code=404, detail="Commitment not found")

    if body.description is not None:
        commitment.description = body.description
    if body.contact_id is not None:
        commitment.contact_id = body.contact_id
    if body.due_date is not None:
        try:
            commitment.due_date = _date.fromisoformat(body.due_date)
        except ValueError:
            pass
    if body.status is not None:
        commitment.status = body.status
        if body.status == "done" and not commitment.completed_at:
            commitment.completed_at = datetime.utcnow()
    await session.flush()
    return {"ok": True}


@router.delete("/commitments/{commitment_id}")
async def delete_commitment(
    commitment_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    result = await session.execute(
        select(Commitment).where(
            and_(Commitment.id == commitment_id, Commitment.user_id == user.id)
        )
    )
    commitment = result.scalar_one_or_none()
    if not commitment:
        raise HTTPException(status_code=404, detail="Commitment not found")
    await session.delete(commitment)
    await session.flush()
    return {"ok": True}


# ─── Feature 11: Life Profile API ─────────────────────────────────────────────

@router.get("/life-profile")
async def get_life_profile(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Return current life profile."""
    result = await session.execute(
        select(LifeProfile).where(LifeProfile.user_id == user.id)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        return {"profile": None}
    return {
        "profile": {
            "id": profile.id,
            "summary": profile.summary,
            "strengths": profile.strengths or [],
            "patterns": profile.patterns or [],
            "current_focus": profile.current_focus,
            "last_updated": profile.last_updated.isoformat() if profile.last_updated else None,
            "update_count": profile.update_count,
        }
    }


@router.post("/life-profile/regenerate")
async def regenerate_life_profile(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Force regenerate life profile now."""
    from bot.core.life_profile import update_life_profile
    profile = await update_life_profile(session, user.id)
    await session.commit()
    return {
        "ok": True,
        "last_updated": profile.last_updated.isoformat() if profile.last_updated else None,
        "update_count": profile.update_count,
    }


# ─── Feature 6: Knowledge Management API ─────────────────────────────────────

class CreateLearningItemBody(BaseModel):
    title: str
    content: Optional[str] = None
    item_type: str = "note"  # book|article|concept|skill|note
    source: Optional[str] = None
    tags: Optional[list] = None


class UpdateLearningItemBody(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    item_type: Optional[str] = None
    source: Optional[str] = None
    tags: Optional[list] = None
    skill_level: Optional[int] = None


class ReviewLearningItemBody(BaseModel):
    quality: int  # 0-5


@router.get("/learning")
async def list_learning_items(
    item_type: Optional[str] = Query(None),
    due_only: bool = Query(False),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """List learning items."""
    q = select(LearningItem).where(LearningItem.user_id == user.id)
    if item_type:
        q = q.where(LearningItem.item_type == item_type)
    if due_only:
        q = q.where(LearningItem.next_review_at <= datetime.utcnow())
    q = q.order_by(LearningItem.next_review_at.asc().nulls_last(), LearningItem.created_at.desc())
    result = await session.execute(q)
    items = result.scalars().all()
    return {
        "items": [
            {
                "id": item.id,
                "title": item.title,
                "content": item.content,
                "item_type": item.item_type,
                "source": item.source,
                "skill_level": item.skill_level,
                "next_review_at": item.next_review_at.isoformat() if item.next_review_at else None,
                "review_count": item.review_count,
                "last_reviewed_at": item.last_reviewed_at.isoformat() if item.last_reviewed_at else None,
                "ease_factor": item.ease_factor,
                "ai_summary": item.ai_summary,
                "tags": item.tags or [],
                "created_at": item.created_at.isoformat(),
            }
            for item in items
        ]
    }


@router.get("/learning/due")
async def get_due_learning_items(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Items due for review today."""
    from bot.core.knowledge import get_due_reviews
    items = await get_due_reviews(session, user.id)
    return {
        "count": len(items),
        "items": [
            {
                "id": item.id,
                "title": item.title,
                "item_type": item.item_type,
                "skill_level": item.skill_level,
                "review_count": item.review_count,
                "ai_summary": item.ai_summary,
                "content": item.content,
                "ease_factor": item.ease_factor,
            }
            for item in items
        ],
    }


@router.get("/learning/skills")
async def get_learning_skills(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Skills with levels."""
    result = await session.execute(
        select(LearningItem).where(
            and_(LearningItem.user_id == user.id, LearningItem.item_type == "skill")
        ).order_by(LearningItem.skill_level.desc(), LearningItem.title.asc())
    )
    skills = result.scalars().all()
    return {
        "skills": [
            {
                "id": s.id,
                "title": s.title,
                "skill_level": s.skill_level,
                "review_count": s.review_count,
                "tags": s.tags or [],
                "next_review_at": s.next_review_at.isoformat() if s.next_review_at else None,
            }
            for s in skills
        ]
    }


@router.post("/learning")
async def create_learning_item(
    body: CreateLearningItemBody,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Add a new learning item."""
    from bot.core.knowledge import add_learning_item
    item = await add_learning_item(
        session=session,
        user_id=user.id,
        title=body.title,
        content=body.content or "",
        item_type=body.item_type,
        source=body.source,
        tags=body.tags,
    )
    await session.commit()
    return {
        "ok": True,
        "id": item.id,
        "ai_summary": item.ai_summary,
        "next_review_at": item.next_review_at.isoformat() if item.next_review_at else None,
    }


@router.put("/learning/{item_id}")
async def update_learning_item(
    item_id: int,
    body: UpdateLearningItemBody,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Update a learning item."""
    result = await session.execute(
        select(LearningItem).where(
            and_(LearningItem.id == item_id, LearningItem.user_id == user.id)
        )
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Learning item not found")
    if body.title is not None:
        item.title = body.title
    if body.content is not None:
        item.content = body.content
    if body.item_type is not None:
        item.item_type = body.item_type
    if body.source is not None:
        item.source = body.source
    if body.tags is not None:
        item.tags = body.tags
    if body.skill_level is not None:
        item.skill_level = max(1, min(5, body.skill_level))
    await session.flush()
    return {"ok": True}


@router.delete("/learning/{item_id}")
async def delete_learning_item(
    item_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Delete a learning item."""
    result = await session.execute(
        select(LearningItem).where(
            and_(LearningItem.id == item_id, LearningItem.user_id == user.id)
        )
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Learning item not found")
    await session.delete(item)
    await session.flush()
    return {"ok": True, "deleted_id": item_id}


@router.post("/learning/{item_id}/review")
async def submit_learning_review(
    item_id: int,
    body: ReviewLearningItemBody,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Submit a spaced repetition review (quality 0-5)."""
    from bot.core.knowledge import review_item
    result = await review_item(session, user.id, item_id, body.quality)
    await session.commit()
    return result


class ProcessMessageBody(BaseModel):
    message: str
    source: str = "api"


@router.post("/process")
async def process_user_message(
    body: ProcessMessageBody,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Process a free-text message through the full GPT-4o 8-dimension pipeline.
    Same as sending a message via Telegram — creates tasks, routines, shopping items etc.
    """
    from bot.ai.client import process_message
    reply = await process_message(session, user, body.message, source=body.source)
    await session.commit()
    return {"ok": True, "reply": reply}


# ─── Onboarding ───────────────────────────────────────────────────────────────

_AREA_TO_CATEGORY: dict[str, str] = {
    "fitness": "fitness",
    "learning": "learning",
    "finance": "finance",
    "relationships": "relationships",
    "health": "health",
    "productivity": "personal",
    "mindset": "mindset",
    "personal": "personal",
}

_MORNING_ROUTINE_TITLES: dict[str, str] = {
    "frueh_aufstehen": "Früh aufstehen",
    "journaling": "Journaling",
    "meditation": "Meditation",
    "sport": "Morgentraining",
    "gesundes_fruehstueck": "Gesundes Frühstück",
}


class OnboardingBody(BaseModel):
    name: Optional[str] = None
    selected_areas: list[str] = []
    first_goal: Optional[str] = None
    wakeup_time: str = "07:00"
    morning_routines: list[str] = []


@router.get("/onboarding/status")
async def get_onboarding_status(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Check if user has completed onboarding (has at least 1 objective and 1 routine, or flag set)."""
    settings = user.settings or {}
    if settings.get("onboarding_completed", False):
        return {"completed": True}

    obj_result = await session.execute(
        select(func.count()).select_from(Objective).where(Objective.user_id == user.id)
    )
    obj_count = obj_result.scalar() or 0

    routine_result = await session.execute(
        select(func.count()).select_from(Routine).where(Routine.user_id == user.id)
    )
    routine_count = routine_result.scalar() or 0

    completed = obj_count > 0 and routine_count > 0
    return {"completed": completed, "objectives": obj_count, "routines": routine_count}


@router.post("/onboarding")
async def complete_onboarding(
    body: OnboardingBody,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Complete onboarding: set name, create first objective, create morning routines."""
    created: dict = {}

    # 1. Update user name
    if body.name:
        stripped = body.name.strip()
        if stripped:
            user.first_name = stripped
            created["name"] = stripped

    # 2. Create first objective
    if body.first_goal:
        category = "personal"
        for area in body.selected_areas:
            if area in _AREA_TO_CATEGORY:
                category = _AREA_TO_CATEGORY[area]
                break

        obj = Objective(
            user_id=user.id,
            title=body.first_goal.strip(),
            category=category,
            status="active",
        )
        session.add(obj)
        await session.flush()
        created["objective_id"] = obj.id
        created["objective_title"] = obj.title

    # 3. Create morning routines
    created_routines = []
    for key in body.morning_routines:
        title = _MORNING_ROUTINE_TITLES.get(key, key)
        routine = Routine(
            user_id=user.id,
            title=title,
            frequency_human="Täglich",
            time_of_day="morning",
            status="active",
        )
        session.add(routine)
        created_routines.append(title)
    if created_routines:
        created["routines"] = created_routines

    # 4. Update settings
    settings = dict(user.settings or {})
    settings["onboarding_completed"] = True
    if body.wakeup_time:
        settings["wakeup_time"] = body.wakeup_time
    user.settings = settings

    await session.commit()
    return {"ok": True, "created": created}


# ─── Push Notifications ──────────────────────────────────────────────────────


@router.get("/push/vapid-key")
async def get_vapid_key(
    user: User = Depends(get_current_user),
) -> dict:
    """Return the VAPID public key for client-side subscription."""
    from bot.config import settings as app_settings
    if not app_settings.vapid_public_key:
        raise HTTPException(status_code=503, detail="Push notifications not configured")
    return {"publicKey": app_settings.vapid_public_key}


class PushSubscribeBody(BaseModel):
    endpoint: str
    keys: dict  # {"p256dh": "...", "auth": "..."}
    userAgent: Optional[str] = None


@router.post("/push/subscribe")
async def push_subscribe(
    body: PushSubscribeBody,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Save a web push subscription for the current user."""
    from bot.database.models import PushSubscription

    p256dh = body.keys.get("p256dh", "")
    auth = body.keys.get("auth", "")
    if not body.endpoint or not p256dh or not auth:
        raise HTTPException(status_code=400, detail="Missing endpoint or keys")

    # Upsert: update if endpoint already exists
    existing = (await session.execute(
        select(PushSubscription).where(and_(
            PushSubscription.user_id == user.id,
            PushSubscription.endpoint == body.endpoint,
        ))
    )).scalar_one_or_none()

    if existing:
        existing.p256dh = p256dh
        existing.auth = auth
        existing.user_agent = body.userAgent
    else:
        session.add(PushSubscription(
            user_id=user.id,
            endpoint=body.endpoint,
            p256dh=p256dh,
            auth=auth,
            user_agent=body.userAgent,
        ))

    await session.commit()
    return {"ok": True}


@router.delete("/push/unsubscribe")
async def push_unsubscribe(
    request: _Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Remove a push subscription by endpoint."""
    from bot.database.models import PushSubscription
    body = await request.json()
    endpoint = body.get("endpoint", "")
    if not endpoint:
        raise HTTPException(status_code=400, detail="Missing endpoint")

    result = await session.execute(
        sql_delete(PushSubscription).where(and_(
            PushSubscription.user_id == user.id,
            PushSubscription.endpoint == endpoint,
        ))
    )
    await session.commit()
    return {"ok": True, "deleted": result.rowcount > 0}


@router.post("/push/test")
async def push_test(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Send a test push notification."""
    from bot.core.push import send_push
    count = await send_push(
        session, user.id,
        title="Personal OS",
        body="Push Notifications funktionieren!",
        tag="test",
    )
    await session.commit()
    return {"ok": True, "sent_to": count}


# ─── Conversational Goal Onboarding (REST API for Dashboard) ─────────────────


class GoalOnboardingStartBody(BaseModel):
    goal_text: str


class GoalOnboardingAnswerBody(BaseModel):
    text: str


@router.post("/goal-onboarding/start")
async def goal_onboarding_start(
    body: GoalOnboardingStartBody,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Start a conversational goal coaching dialog. Returns first question."""
    from bot.core.goal_onboarding import start_onboarding, get_active_onboarding
    existing = await get_active_onboarding(session, user.id)
    if existing:
        existing.status = "cancelled"
        await session.flush()

    onboarding, intro = await start_onboarding(session, user.id, body.goal_text)
    await session.commit()
    return {"onboarding_id": onboarding.id, "message": intro, "status": onboarding.status, "step": onboarding.current_step}


@router.get("/goal-onboarding/active")
async def goal_onboarding_active(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Get the active onboarding session, if any."""
    from bot.core.goal_onboarding import get_active_onboarding
    onboarding = await get_active_onboarding(session, user.id)
    if not onboarding:
        return {"active": False}
    return {
        "active": True,
        "onboarding_id": onboarding.id,
        "status": onboarding.status,
        "step": onboarding.current_step,
        "goal": onboarding.goal_input,
        "draft_payload": onboarding.draft_payload,
    }


@router.post("/goal-onboarding/answer")
async def goal_onboarding_answer(
    body: GoalOnboardingAnswerBody,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Process an answer in the coaching dialog. Returns next question or plan."""
    from bot.core.goal_onboarding import get_active_onboarding, handle_onboarding_answer
    onboarding = await get_active_onboarding(session, user.id)
    if not onboarding:
        raise HTTPException(status_code=404, detail="Kein aktives Onboarding")

    reply_text, keyboard_data = await handle_onboarding_answer(session, user, onboarding, body.text)
    await session.commit()

    return {
        "message": reply_text,
        "status": onboarding.status,
        "step": onboarding.current_step,
        "buttons": keyboard_data,
        "draft_payload": onboarding.draft_payload if onboarding.status == "plan_review" else None,
    }


@router.post("/goal-onboarding/confirm")
async def goal_onboarding_confirm(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Confirm and execute the generated plan."""
    from bot.core.goal_onboarding import get_active_onboarding, handle_onboarding_callback
    onboarding = await get_active_onboarding(session, user.id)
    if not onboarding:
        raise HTTPException(status_code=404, detail="Kein aktives Onboarding")

    reply = await handle_onboarding_callback(session, user, onboarding, f"goal_confirm_{onboarding.id}")
    await session.commit()
    return {"message": reply, "status": onboarding.status}


@router.post("/goal-onboarding/adjust")
async def goal_onboarding_adjust(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Request plan adjustment."""
    from bot.core.goal_onboarding import get_active_onboarding, handle_onboarding_callback
    onboarding = await get_active_onboarding(session, user.id)
    if not onboarding:
        raise HTTPException(status_code=404, detail="Kein aktives Onboarding")

    reply = await handle_onboarding_callback(session, user, onboarding, f"goal_adjust_{onboarding.id}")
    await session.commit()
    return {"message": reply, "status": onboarding.status}


@router.post("/goal-onboarding/cancel")
async def goal_onboarding_cancel(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Cancel the active onboarding."""
    from bot.core.goal_onboarding import cancel_onboarding
    cancelled = await cancel_onboarding(session, user.id)
    await session.commit()
    return {"ok": True, "cancelled": cancelled}


# ─── Nutrition Endpoints ──────────────────────────────────────────────────────

@router.get("/nutrition/daily")
async def get_nutrition_daily(
    date: Optional[str] = None,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Get daily nutrition summary with macro totals and meal breakdown."""
    from bot.core.nutrition import get_daily_nutrition
    from datetime import date as date_cls
    target_date = None
    if date:
        try:
            target_date = date_cls.fromisoformat(date)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    return await get_daily_nutrition(session, user.id, target_date)


@router.get("/nutrition/history")
async def get_nutrition_history_endpoint(
    days: int = 30,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list:
    """Get nutrition history (per-day aggregates) for the last N days."""
    from bot.core.nutrition import get_nutrition_history
    days = min(max(days, 1), 365)
    return await get_nutrition_history(session, user.id, days)


@router.post("/nutrition/log")
async def log_nutrition(
    body: dict,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Log a food entry with structured nutrition data."""
    from bot.core.nutrition import create_food_entry
    from datetime import date as date_cls
    logged_date = None
    if body.get("logged_date"):
        try:
            logged_date = date_cls.fromisoformat(body["logged_date"])
        except ValueError:
            pass
    entry = await create_food_entry(
        session,
        user_id=user.id,
        food_name=body.get("food_name", "Unbekannt"),
        meal_type=body.get("meal_type", "snack"),
        quantity=body.get("quantity"),
        unit=body.get("unit"),
        calories=body.get("calories"),
        protein_g=body.get("protein_g"),
        carbs_g=body.get("carbs_g"),
        fat_g=body.get("fat_g"),
        fiber_g=body.get("fiber_g"),
        sodium_mg=body.get("sodium_mg"),
        sugar_g=body.get("sugar_g"),
        notes=body.get("notes"),
        source=body.get("source", "api"),
        logged_date=logged_date,
    )
    await session.commit()
    return {
        "id": entry.id,
        "food_name": entry.food_name,
        "meal_type": entry.meal_type,
        "calories": entry.calories,
        "protein_g": entry.protein_g,
        "carbs_g": entry.carbs_g,
        "fat_g": entry.fat_g,
        "sodium_mg": entry.sodium_mg,
        "logged_date": entry.logged_date.isoformat(),
    }


@router.get("/nutrition/baseline/{metric_key}")
async def get_nutrition_baseline(
    metric_key: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Get personal baseline for a metric (anomaly detection context)."""
    from bot.core.personal_baseline import get_cached_baseline
    baseline = await get_cached_baseline(session, user.id, metric_key)
    if not baseline:
        return {"metric_key": metric_key, "status": "no_data", "days_tracked": 0}
    return {
        "metric_key": baseline.metric_key,
        "mean_30d": baseline.mean_30d,
        "std_30d": baseline.std_30d,
        "mean_90d": baseline.mean_90d,
        "min_ever": baseline.min_ever,
        "max_ever": baseline.max_ever,
        "days_tracked": baseline.days_tracked,
        "last_updated": baseline.last_updated.isoformat() if baseline.last_updated else None,
    }


# ─── Life Context Endpoints ───────────────────────────────────────────────────

@router.get("/life-context")
async def get_life_context(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Get current life mode."""
    from bot.core.life_context import get_active_life_mode, get_life_mode_config
    config = await get_life_mode_config(session, user.id)
    return config


@router.post("/life-context")
async def set_life_context(
    body: dict,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Set life mode (normal/travel/sick/vacation/intense/recovery)."""
    from bot.core.life_context import set_life_mode, format_life_mode_message
    from datetime import date as date_cls
    active_until = None
    if body.get("active_until"):
        try:
            active_until = date_cls.fromisoformat(body["active_until"])
        except ValueError:
            pass
    ctx = await set_life_mode(
        session, user.id,
        mode=body.get("mode", "normal"),
        notes=body.get("notes"),
        active_until=active_until,
    )
    await session.commit()
    return {
        "mode": ctx.mode,
        "notes": ctx.notes,
        "active_from": ctx.active_from.isoformat(),
        "active_until": ctx.active_until.isoformat() if ctx.active_until else None,
        "message": format_life_mode_message(ctx.mode, ctx.notes, ctx.active_until),
    }


# ─── Watch / Voice Endpoints ──────────────────────────────────────────────────

@router.get("/watch/face")
async def get_watch_face(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Compact real-time data for watch complications and tiles.

    Designed for minimal payload that any watch/widget can poll.
    Updates every ~15 min from wearable background sync.
    """
    today = date.today()
    today_dt = datetime.combine(today, datetime.min.time())

    # ── Today's health logs ─────────────────────────────────────────────────
    logs_res = await session.execute(
        select(Log).where(
            and_(
                Log.user_id == user.id,
                Log.created_at >= today_dt,
            )
        )
    )
    logs = logs_res.scalars().all()

    steps = calories = hrv = mood = water_ml = 0
    sleep_hours = None
    for log in logs:
        d = log.data or {}
        if log.log_type == "steps":
            steps = max(steps, int(d.get("count", 0)))
        elif log.log_type == "calories":
            calories = max(calories, int(d.get("kcal", 0)))
        elif log.log_type == "hrv":
            hrv = max(hrv, int(d.get("ms", 0)))
        elif log.log_type == "mood":
            mood = max(mood, int(d.get("score", 0)))
        elif log.log_type == "water":
            water_ml += int(d.get("ml", d.get("amount_l", 0) * 1000))
        elif log.log_type == "sleep" and sleep_hours is None:
            sleep_hours = float(d.get("hours", 0))

    # ── Streak (longest active habit streak) ───────────────────────────────
    streaks_res = await session.execute(
        select(KeyResult).where(
            and_(
                KeyResult.user_id == user.id,
                KeyResult.kr_type == "habit",
                KeyResult.current_value > 0,
            )
        ).order_by(KeyResult.current_value.desc()).limit(1)
    )
    top_kr = streaks_res.scalars().first()
    streak = int(top_kr.current_value) if top_kr else 0
    streak_label = top_kr.title[:20] if top_kr else ""

    # ── Next action ─────────────────────────────────────────────────────────
    from bot.core.completion_hooks import get_next_unblocked_action
    next_task = await get_next_unblocked_action(session, user.id)
    next_action = next_task.get("title", "")[:40] if next_task else "Alles erledigt ✓"

    # ── Tasks completed today ───────────────────────────────────────────────
    from bot.database.models import Task
    tasks_done_res = await session.execute(
        select(func.count(Task.id)).where(
            and_(
                Task.user_id == user.id,
                Task.status == "done",
                Task.updated_at >= today_dt,
            )
        )
    )
    tasks_done = int(tasks_done_res.scalar() or 0)

    # ── Routines completion ─────────────────────────────────────────────────
    completions = await get_todays_completions(session, user.id)
    active_routines = await get_active_routines(session, user.id)
    routines_done = len(completions)
    routines_total = len(active_routines)

    # ── Life mode ───────────────────────────────────────────────────────────
    from bot.core.life_context import get_active_life_mode
    life_mode = await get_active_life_mode(session, user.id)

    # ── Simple daily score (0–100) ──────────────────────────────────────────
    score_parts = []
    if steps >= 8000:
        score_parts.append(25)
    elif steps >= 4000:
        score_parts.append(12)
    if sleep_hours and sleep_hours >= 7:
        score_parts.append(25)
    elif sleep_hours and sleep_hours >= 5:
        score_parts.append(10)
    if routines_total > 0:
        score_parts.append(int(25 * routines_done / routines_total))
    if mood >= 7:
        score_parts.append(25)
    elif mood >= 4:
        score_parts.append(12)
    daily_score = min(100, sum(score_parts))

    return {
        "next_action": next_action,
        "streak": streak,
        "streak_label": streak_label,
        "steps": steps,
        "calories": calories,
        "hrv_ms": hrv,
        "mood": mood,
        "water_ml": water_ml,
        "sleep_hours": sleep_hours,
        "tasks_done_today": tasks_done,
        "routines_done": routines_done,
        "routines_total": routines_total,
        "daily_score": daily_score,
        "life_mode": life_mode,
        "updated_at": datetime.utcnow().isoformat() + "Z",
    }


@router.post("/voice/command")
async def voice_command(
    audio: Optional[UploadFile] = File(None),
    text: Optional[str] = Form(None),
    source: str = Form("watch"),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Voice command endpoint for watch/wearable integration.

    Accepts either:
    - Multipart audio file (WAV/M4A/MP3/WEBM) → Whisper transcription → GPT-4o COO
    - Plain text (already transcribed on device) → GPT-4o COO

    Returns transcribed text + AI response (speak this back via TTS on device).
    """
    from bot.ai.client import openai_client, process_message

    transcribed = text or ""

    # ── Whisper transcription ────────────────────────────────────────────────
    if audio and not transcribed:
        audio_bytes = await audio.read()
        if len(audio_bytes) > 25 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="Audio too large (max 25 MB)")

        import io as _io
        audio_buffer = _io.BytesIO(audio_bytes)
        audio_buffer.name = audio.filename or "voice.m4a"

        whisper_resp = await openai_client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_buffer,
            language="de",
        )
        transcribed = whisper_resp.text.strip()

    if not transcribed:
        raise HTTPException(status_code=400, detail="Kein Text oder Audio übermittelt")

    # ── Process through full GPT-4o COO pipeline ────────────────────────────
    reply = await process_message(session, user, transcribed, source=f"voice_{source}")
    await session.commit()

    return {
        "ok": True,
        "transcribed": transcribed,
        "response": reply,
        "source": source,
    }
