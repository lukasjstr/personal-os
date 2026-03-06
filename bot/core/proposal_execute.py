"""CORE-2/3/4: Execute an accepted OKR proposal draft into real DB objects.

This module is intentionally conservative:
- Only runs after explicit approval (draft.status == 'accepted').
- Creates Objective + KeyResults + Tasks from the draft payload.
- Also materializes *preview* artifacts into real execution artifacts:
  - CalendarEvent blocks derived from slot candidates (CORE-3)
  - ScheduledReminder rows derived from reminder drafts (CORE-4)

Notes:
- The slot/reminder generators are pure/read-only; here we persist their outputs.
- We keep logic minimal; conflict detection and advanced scheduling can be added later.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import (
    CalendarEvent,
    KeyResult,
    Objective,
    OKRProposalDraft,
    ScheduledReminder,
    Task,
)


@dataclass
class ExecuteResult:
    objective_id: int
    key_result_ids: list[int]
    task_ids: list[int]
    calendar_event_ids: list[int]
    scheduled_reminder_ids: list[int]


def _safe_int(x: Any, default: int = 0) -> int:
    try:
        return int(x)
    except Exception:
        return default


def _extract_first_objective(draft_payload: dict[str, Any]) -> dict[str, Any] | None:
    objs = draft_payload.get("objectives")
    if not isinstance(objs, list) or not objs:
        return None
    obj = objs[0]
    return obj if isinstance(obj, dict) else None


async def execute_accepted_proposal(
    session: AsyncSession,
    draft_row: OKRProposalDraft,
) -> ExecuteResult:
    """Execute one accepted proposal draft.

    Idempotency: if we already created an Objective with a marker referencing this draft,
    we return the existing objects. For now we use a simple description marker.
    """

    from bot.core.slot_candidates import derive_slot_candidates
    from bot.core.reminder_factory import generate_reminder_drafts

    marker = f"[proposal_draft_id:{draft_row.id}]"

    # If already executed, return existing ids.
    existing_obj_res = await session.execute(
        select(Objective)
        .where(and_(Objective.user_id == draft_row.user_id, Objective.description.ilike(f"%{marker}%")))
        .order_by(Objective.id.desc())
        .limit(1)
    )
    existing_obj = existing_obj_res.scalar_one_or_none()
    if existing_obj is not None:
        # Collect related objects best-effort
        kr_res = await session.execute(
            select(KeyResult.id).where(KeyResult.objective_id == existing_obj.id)
        )
        task_res = await session.execute(
            select(Task.id).where(Task.objective_id == existing_obj.id)
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
            objective_id=existing_obj.id,
            key_result_ids=list(kr_res.scalars().all()),
            task_ids=list(task_res.scalars().all()),
            calendar_event_ids=list(ev_res.scalars().all()),
            scheduled_reminder_ids=list(rem_res.scalars().all()),
        )

    obj_d = _extract_first_objective(draft_row.draft_payload) or {}
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

    # Key results
    key_result_ids: list[int] = []
    for kr in (obj_d.get("key_results") or []):
        if not isinstance(kr, dict):
            continue
        kr_title = str(kr.get("title") or "Key Result").strip()
        target_value = float(kr.get("target_value") or 1)
        current_value = float(kr.get("current_value") or 0)
        unit = str(kr.get("unit") or "")
        frequency = str(kr.get("frequency") or "weekly")
        kr_row = KeyResult(
            objective_id=objective.id,
            user_id=draft_row.user_id,
            title=kr_title,
            type=str(kr.get("type") or "number"),
            current_value=current_value,
            target_value=target_value,
            unit=unit,
            frequency=frequency,
            status="active",
        )
        session.add(kr_row)
        await session.flush()
        key_result_ids.append(kr_row.id)

    # Tasks (best-effort: from draft payload tasks list, or derive none)
    task_ids: list[int] = []
    for t in (obj_d.get("tasks") or []):
        if not isinstance(t, dict):
            continue
        t_title = str(t.get("title") or "Task").strip()
        if not t_title:
            continue
        task = Task(
            user_id=draft_row.user_id,
            title=t_title,
            category=str(t.get("category") or category),
            priority=_safe_int(t.get("priority"), 2),
            status="open",
            objective_id=objective.id,
        )
        session.add(task)
        await session.flush()
        task_ids.append(task.id)

    # Calendar blocks: materialize slot candidates as CalendarEvent.
    calendar_event_ids: list[int] = []
    for c in derive_slot_candidates(draft_row.draft_payload):
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

    # Reminders: materialize reminder drafts into ScheduledReminder rows.
    scheduled_reminder_ids: list[int] = []
    for r in generate_reminder_drafts(draft_row.draft_payload):
        msg = (r.body or "").strip()
        if marker not in msg:
            msg = (msg + "\n\n" + marker).strip()
        rem = ScheduledReminder(
            user_id=draft_row.user_id,
            reminder_type="progress_nudge",
            message=msg,
            scheduled_for=r.scheduled_at,
            repeat_rule=r.cron,
            status="pending",
            auto_generated=True,
        )
        session.add(rem)
        await session.flush()
        scheduled_reminder_ids.append(rem.id)

    # Mark draft as executed.
    draft_row.status = "executed"
    await session.commit()

    return ExecuteResult(
        objective_id=objective.id,
        key_result_ids=key_result_ids,
        task_ids=task_ids,
        calendar_event_ids=calendar_event_ids,
        scheduled_reminder_ids=scheduled_reminder_ids,
    )
