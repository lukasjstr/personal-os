"""Life Planner — derives routines, shopping tasks, and calendar milestones from an accepted OKR.

Called automatically after proposal_execute to close the loop:
  Goal Input → OKR → Tasks (with due dates) → Routines → Shopping → Calendar blocks
"""
import logging
from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import CalendarEvent, KeyResult, Routine, Task

logger = logging.getLogger(__name__)


async def derive_life_artifacts(
    session: AsyncSession,
    user_id: int,
    draft_payload: dict,
    objective_id: int,
    kr_title_to_id: dict[str, int],
) -> dict:
    """Derive routines, shopping tasks, and calendar milestone events from an OKR draft payload.

    Extracts:
    - routines[] or weekly_schedule[] → Routine rows linked to KRs
    - shopping_items[] → Task rows (category=shopping)
    - tasks with due_date → CalendarEvent milestone rows

    Returns counts of created objects.
    """
    routine_ids: list[int] = []
    shopping_task_ids: list[int] = []
    calendar_ids: list[int] = []

    # ── 1. Routines ───────────────────────────────────────────────────────────
    routines_data: list[dict] = draft_payload.get("routines") or []

    # Fall back to weekly_schedule if no explicit routines
    if not routines_data:
        for entry in (draft_payload.get("weekly_schedule") or []):
            if not isinstance(entry, dict):
                continue
            activity = str(entry.get("activity") or "").strip()
            if not activity:
                continue
            day = str(entry.get("day") or "")
            routines_data.append({
                "title": activity,
                "frequency": f"Jeden {day}" if day else "wöchentlich",
                "time_of_day": "anytime",
                "duration_min": int(entry.get("duration_min") or 30),
            })

    for r_data in routines_data:
        if not isinstance(r_data, dict):
            continue
        title = str(r_data.get("title") or "").strip()
        if not title or len(title) < 3:
            continue

        freq = str(r_data.get("frequency") or "wöchentlich")
        raw_tod = str(r_data.get("time_of_day") or "anytime").lower()
        tod = raw_tod if raw_tod in ("morning", "midday", "evening", "anytime") else "anytime"

        # Link to KR by hint
        linked_kr_id: Optional[int] = None
        kr_hint = str(r_data.get("kr_title") or "").lower().strip()
        if kr_hint and kr_title_to_id:
            for kr_t, kr_id in kr_title_to_id.items():
                if kr_hint in kr_t or kr_t in kr_hint:
                    linked_kr_id = kr_id
                    break

        routine = Routine(
            user_id=user_id,
            title=title,
            frequency_human=freq,
            time_of_day=tod,
            status="active",
            linked_key_result_id=linked_kr_id,
        )
        session.add(routine)
        await session.flush()
        routine_ids.append(routine.id)
        logger.info("Life planner: created routine %d '%s' for user %d", routine.id, title, user_id)

    # ── 2. Shopping items ─────────────────────────────────────────────────────
    for item in (draft_payload.get("shopping_items") or []):
        if not isinstance(item, str) or not item.strip():
            continue
        task = Task(
            user_id=user_id,
            objective_id=objective_id,
            title=item.strip()[:200],
            category="shopping",
            priority=3,
            status="todo",
        )
        session.add(task)
        await session.flush()
        shopping_task_ids.append(task.id)
        logger.info("Life planner: created shopping task %d '%s' for user %d", task.id, item, user_id)

    # ── 3. Calendar milestone blocks for key tasks ────────────────────────────
    # For tasks in the plan that have due_days set, create a CalendarEvent milestone
    today = date.today()
    for t_data in (draft_payload.get("tasks") or []):
        if not isinstance(t_data, dict):
            continue
        due_days = int(t_data.get("due_days") or 0)
        if due_days <= 0:
            continue
        title = str(t_data.get("title") or "").strip()
        if not title:
            continue

        milestone_date = today + timedelta(days=due_days)
        # Only create milestones for future dates
        if milestone_date <= today:
            continue

        # Milestone: all-day event on due date
        milestone_dt = datetime.combine(milestone_date, datetime.min.time().replace(hour=9))
        ev = CalendarEvent(
            user_id=user_id,
            title=f"📌 {title}",
            description=f"Meilenstein aus OKR-Plan",
            start_time=milestone_dt,
            end_time=milestone_dt.replace(hour=10),
            all_day=False,
            event_type="deadline",
        )
        session.add(ev)
        await session.flush()
        calendar_ids.append(ev.id)

    logger.info(
        "Life planner: user %d — %d routines, %d shopping items, %d milestones",
        user_id, len(routine_ids), len(shopping_task_ids), len(calendar_ids),
    )
    return {
        "routine_ids": routine_ids,
        "shopping_task_ids": shopping_task_ids,
        "calendar_milestone_ids": calendar_ids,
    }
