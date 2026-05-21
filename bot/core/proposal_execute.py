"""CORE-2/3/4: Execute an accepted OKR proposal draft into real DB objects.

This module is intentionally conservative:
- Only runs after explicit approval (draft.status == 'accepted').
- Creates Objective + KeyResults + Tasks from the draft payload.
- Also materializes *preview* artifacts into real execution artifacts:
  - CalendarEvent blocks derived from slot candidates (CORE-3)
  - ScheduledReminder rows derived from reminder drafts (CORE-4)

Notes:
- The slot/reminder generators are pure/read-only; here we persist their outputs.
- Idempotency is enforced via draft.executed_at + draft.executed_objective_id.
- Calendar conflict detection skips slots that overlap existing events.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import (
    AutopilotNotification,
    CalendarEvent,
    KeyResult,
    Objective,
    OKRProposalDraft,
    ScheduledReminder,
    Task,
)

logger = logging.getLogger(__name__)

_REMINDER_KIND_MAP: dict[str, str] = {
    "task_due": "task_due",
    "checkin": "daily_checkin",
    "milestone": "milestone",
    "routine": "routine_nudge",
}


@dataclass
class ExecuteResult:
    objective_id: int
    key_result_ids: list[int]
    task_ids: list[int]
    calendar_event_ids: list[int]
    scheduled_reminder_ids: list[int]
    calendar_conflicts: list[int] = field(default_factory=list)


def _safe_int(x: Any, default: int = 0) -> int:
    try:
        return int(x)
    except Exception:
        return default


def _extract_plan(draft_payload: dict[str, Any]) -> tuple[dict[str, Any], list[dict], list[dict]]:
    """Return (objective_dict, key_results_list, tasks_list) from either payload format.

    New format (from /goals/generate):
        {"objective": {...}, "key_results": [...], "tasks": [...]}

    Legacy format (from /objectives/okr-draft):
        {"objectives": [{"title": ..., "key_results": [...], "tasks": [...]}]}
    """
    # New flat format
    if isinstance(draft_payload.get("objective"), dict):
        obj_d = draft_payload["objective"]
        krs = draft_payload.get("key_results") or obj_d.get("key_results") or []
        tasks = draft_payload.get("tasks") or obj_d.get("tasks") or []
        return obj_d, krs, tasks

    # Legacy format
    objs = draft_payload.get("objectives")
    if isinstance(objs, list) and objs and isinstance(objs[0], dict):
        obj_d = objs[0]
        return obj_d, obj_d.get("key_results") or [], obj_d.get("tasks") or []

    return {}, [], []


async def execute_accepted_proposal(
    session: AsyncSession,
    draft_row: OKRProposalDraft,
) -> ExecuteResult:
    """Execute one accepted proposal draft.

    Idempotency: if draft.executed_at and draft.executed_objective_id are set,
    the draft was already executed — return the existing object IDs immediately.
    """

    from bot.core.slot_candidates import derive_slot_candidates
    from bot.core.reminder_factory import generate_reminder_drafts

    marker = f"[proposal_draft_id:{draft_row.id}]"

    # --- Idempotency guard (fast path) ---
    if draft_row.executed_at is not None and draft_row.executed_objective_id is not None:
        existing_obj_id = draft_row.executed_objective_id
        kr_res = await session.execute(
            select(KeyResult.id).where(KeyResult.objective_id == existing_obj_id)
        )
        task_res = await session.execute(
            select(Task.id).where(Task.objective_id == existing_obj_id)
        )
        ev_res = await session.execute(
            select(CalendarEvent.id).where(
                and_(
                    CalendarEvent.user_id == draft_row.user_id,
                    CalendarEvent.description.ilike(f"%{marker}%"),
                )
            )
        )
        rem_res = await session.execute(
            select(ScheduledReminder.id).where(
                and_(
                    ScheduledReminder.user_id == draft_row.user_id,
                    ScheduledReminder.message.ilike(f"%{marker}%"),
                )
            )
        )
        return ExecuteResult(
            objective_id=existing_obj_id,
            key_result_ids=list(kr_res.scalars().all()),
            task_ids=list(task_res.scalars().all()),
            calendar_event_ids=list(ev_res.scalars().all()),
            scheduled_reminder_ids=list(rem_res.scalars().all()),
            calendar_conflicts=[],
        )

    obj_d, raw_krs, raw_tasks = _extract_plan(draft_row.draft_payload)
    title = str(obj_d.get("title") or draft_row.source_text[:80] or "New Objective").strip()
    category = str(obj_d.get("category") or "personal")
    description = (str(obj_d.get("description") or "").strip() + "\n\n" + marker).strip()

    objective = Objective(
        user_id=draft_row.user_id,
        title=title,
        description=description,
        category=category,
        status="active",
        priority_weight=_safe_int(obj_d.get("priority_weight"), 5),
    )
    session.add(objective)
    await session.flush()

    # Key results — build title→id map for task linkage
    key_result_ids: list[int] = []
    kr_title_to_id: dict[str, int] = {}
    for kr in raw_krs:
        if not isinstance(kr, dict):
            continue
        kr_title = str(kr.get("title") or "Key Result").strip()
        target_value = float(kr.get("target_value") or 1)
        current_value = float(kr.get("current_value") or 0)
        unit = str(kr.get("unit") or "")
        metric_type = str(kr.get("metric_type") or kr.get("type") or "number")
        kr_row = KeyResult(
            objective_id=objective.id,
            user_id=draft_row.user_id,
            title=kr_title,
            metric_type=metric_type,
            current_value=current_value,
            target_value=target_value,
            unit=unit,
            frequency=str(kr.get("frequency") or "weekly"),
            status="active",
        )
        session.add(kr_row)
        await session.flush()
        key_result_ids.append(kr_row.id)
        kr_title_to_id[kr_title.lower()] = kr_row.id

    # Tasks — linked to best-matching KR where possible
    task_ids: list[int] = []
    default_kr_id = key_result_ids[0] if key_result_ids else None
    for t in raw_tasks:
        if not isinstance(t, dict):
            continue
        t_title = str(t.get("title") or "Task").strip()
        if not t_title:
            continue
        # Link to KR: explicit kr_title field, or fall back to first KR
        linked_kr_id: int | None = None
        t_kr_hint = str(t.get("kr_title") or t.get("key_result") or "").lower().strip()
        if t_kr_hint:
            for kr_t, kr_id in kr_title_to_id.items():
                if t_kr_hint in kr_t or kr_t in t_kr_hint:
                    linked_kr_id = kr_id
                    break
        if linked_kr_id is None:
            linked_kr_id = default_kr_id
        from datetime import date as _date, timedelta as _timedelta
        due_days = _safe_int(t.get("due_days"), 0)
        task_due_date = (_date.today() + _timedelta(days=due_days)) if due_days > 0 else None
        task = Task(
            user_id=draft_row.user_id,
            title=t_title,
            category=str(t.get("category") or category),
            priority=_safe_int(t.get("priority"), 2),
            status="todo",
            objective_id=objective.id,
            key_result_id=linked_kr_id,
            due_date=task_due_date,
        )
        session.add(task)
        await session.flush()
        task_ids.append(task.id)

    # V3 P04 — for every task with a due_date, create a deadline CalendarEvent.
    # Idempotent: keyed by ical_uid = f"task-deadline-{task_id}@personal-os".
    calendar_event_ids: list[int] = []
    calendar_conflicts: list[int] = []
    from datetime import datetime as _dt2
    for task_id in task_ids:
        task_row = await session.get(Task, task_id)
        if task_row is None or task_row.due_date is None:
            continue
        ical_uid = f"task-deadline-{task_id}@personal-os"
        existing = await session.execute(
            select(CalendarEvent.id).where(CalendarEvent.ical_uid == ical_uid).limit(1)
        )
        if existing.scalar_one_or_none() is not None:
            continue
        deadline_start = _dt2.combine(task_row.due_date, _dt2.min.time().replace(hour=10))
        ev = CalendarEvent(
            user_id=draft_row.user_id,
            title=f"⏰ {task_row.title}",
            description=f"Deadline für Task#{task_id}\n\n{marker}",
            start_time=deadline_start,
            end_time=deadline_start.replace(hour=11),
            all_day=False,
            event_type="deadline",
            linked_task_id=task_id,
            ical_uid=ical_uid,
        )
        session.add(ev)
        try:
            await session.flush()
            calendar_event_ids.append(ev.id)
        except Exception:
            await session.rollback()
            logger.info("Task-deadline calendar event already exists for task %d", task_id)

    # Calendar blocks: materialize slot candidates as CalendarEvent.
    # Skip slots that overlap existing calendar events for this user.
    for c in derive_slot_candidates(draft_row.draft_payload):
        # Conflict detection: check for overlapping events
        conflict_res = await session.execute(
            select(CalendarEvent.id).where(
                and_(
                    CalendarEvent.user_id == draft_row.user_id,
                    CalendarEvent.start_time < c.ends_at,
                    CalendarEvent.end_time > c.starts_at,
                )
            ).limit(1)
        )
        conflict_id = conflict_res.scalar_one_or_none()
        if conflict_id is not None:
            logger.warning(
                "Calendar conflict for draft %d slot '%s' (%s–%s): "
                "overlaps event id=%d",
                draft_row.id, c.title, c.starts_at, c.ends_at, conflict_id,
            )
            # V3 P04 — surface conflict as actionable notification in the dashboard.
            existing_event = (await session.execute(
                select(CalendarEvent).where(CalendarEvent.id == conflict_id)
            )).scalar_one_or_none()
            existing_title = existing_event.title if existing_event else "anderer Termin"
            session.add(AutopilotNotification(
                user_id=draft_row.user_id,
                notification_type="calendar_conflict",
                title=f"Slot-Konflikt: {c.title}",
                body=(
                    f"'{c.title}' ({c.starts_at:%d.%m %H:%M}–{c.ends_at:%H:%M}) "
                    f"überschneidet '{existing_title}'.\n\n{marker}"
                ),
                status="pending",
                source="proposal_execute",
            ))
            await session.flush()
            calendar_conflicts.append(len(calendar_event_ids) + len(calendar_conflicts))
            continue

        ev = CalendarEvent(
            user_id=draft_row.user_id,
            title=c.title,
            description=(c.notes or "") + ("\n\n" + marker),
            start_time=c.starts_at,
            end_time=c.ends_at,
            all_day=False,
            event_type="reminder",
        )
        session.add(ev)
        await session.flush()
        calendar_event_ids.append(ev.id)

    # Reminders: first materialize explicit "reminders" array from new payload format.
    scheduled_reminder_ids: list[int] = []
    from datetime import date as _date, timedelta
    today = _date.today()
    for r_dict in (draft_row.draft_payload.get("reminders") or []):
        if not isinstance(r_dict, dict):
            continue
        title = str(r_dict.get("title") or "Erinnerung")
        message = str(r_dict.get("message") or title).strip()
        if marker not in message:
            message = (message + "\n\n" + marker).strip()
        day_offset = _safe_int(r_dict.get("day_offset"), 1)
        time_str = str(r_dict.get("time") or "09:00")
        try:
            h, m = (int(x) for x in time_str.split(":")[:2])
        except Exception:
            h, m = 9, 0
        from datetime import datetime as _dt
        sched_date = today + timedelta(days=day_offset)
        scheduled_for = _dt(sched_date.year, sched_date.month, sched_date.day, h, m)
        rem = ScheduledReminder(
            user_id=draft_row.user_id,
            reminder_type="milestone",
            message=message,
            scheduled_for=scheduled_for,
            status="pending",
            auto_generated=True,
        )
        session.add(rem)
        await session.flush()
        scheduled_reminder_ids.append(rem.id)

    # Also materialize reminder drafts from reminder_factory (calendar/legacy flow).
    for r in generate_reminder_drafts(draft_row.draft_payload):
        msg = (r.body or "").strip()
        if marker not in msg:
            msg = (msg + "\n\n" + marker).strip()
        reminder_kind = getattr(r, "kind", None) or ""
        reminder_type = _REMINDER_KIND_MAP.get(reminder_kind, "generic")
        rem = ScheduledReminder(
            user_id=draft_row.user_id,
            reminder_type=reminder_type,
            message=msg,
            scheduled_for=r.scheduled_at,
            repeat_rule=r.cron,
            status="pending",
            auto_generated=True,
        )
        session.add(rem)
        await session.flush()
        scheduled_reminder_ids.append(rem.id)

    # Mark draft as executed and stamp idempotency fields.
    draft_row.status = "executed"
    draft_row.executed_at = datetime.utcnow()
    draft_row.executed_objective_id = objective.id
    await session.commit()

    # Derive life artifacts (routines, shopping, calendar milestones)
    try:
        from bot.core.life_planner import derive_life_artifacts
        await derive_life_artifacts(
            session, draft_row.user_id, draft_row.draft_payload, objective.id, kr_title_to_id
        )
        await session.commit()
    except Exception:
        logger.exception("Life artifact derivation failed for draft %d (non-fatal)", draft_row.id)

    return ExecuteResult(
        objective_id=objective.id,
        key_result_ids=key_result_ids,
        task_ids=task_ids,
        calendar_event_ids=calendar_event_ids,
        scheduled_reminder_ids=scheduled_reminder_ids,
        calendar_conflicts=calendar_conflicts,
    )
