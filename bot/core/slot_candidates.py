"""CORE-3b: Pure slot candidate generator (read-only, no side-effects)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from bot.core.okr_generator import DraftObjective, OKRDraft


@dataclass
class SlotCandidate:
    title: str
    starts_at: datetime
    ends_at: datetime
    slot_type: str
    notes: str = ""
    source_objective: str = ""
    source_key_result: str = ""


_FREQUENCY_DURATION_MINUTES: dict[str, int] = {
    "daily": 30,
    "weekly": 60,
    "monthly": 90,
    "once": 120,
}

_FREQUENCY_INTERVAL_DAYS: dict[str, int] = {
    "daily": 1,
    "weekly": 7,
    "monthly": 30,
    "once": 0,
}


def derive_slot_candidates(
    draft_payload: dict[str, Any],
    anchor: datetime | None = None,
    horizon_days: int = 90,
) -> list[SlotCandidate]:
    """Derive calendar slot candidates from an OKR draft payload without any I/O."""
    if anchor is None:
        anchor = datetime.utcnow().replace(hour=9, minute=0, second=0, microsecond=0)
    horizon_end = anchor + timedelta(days=horizon_days)

    try:
        draft = OKRDraft.model_validate(draft_payload)
    except Exception:
        return []

    candidates: list[SlotCandidate] = []
    for obj in draft.objectives:
        candidates.extend(_slots_for_objective(obj, anchor, horizon_end))

    candidates.sort(key=lambda s: s.starts_at)
    return candidates


def _slots_for_objective(obj: DraftObjective, anchor: datetime, horizon_end: datetime) -> list[SlotCandidate]:
    slots: list[SlotCandidate] = []

    if obj.target_date is not None:
        deadline_dt = datetime.combine(obj.target_date, anchor.timetz()).replace(
            hour=10, minute=0, second=0, microsecond=0
        )
        if anchor <= deadline_dt <= horizon_end:
            slots.append(
                SlotCandidate(
                    title=f"Review: {obj.title}",
                    starts_at=deadline_dt,
                    ends_at=deadline_dt + timedelta(minutes=30),
                    slot_type="deadline_review",
                    notes=f"Deadline review for objective '{obj.title}'",
                    source_objective=obj.title,
                )
            )

    for kr in obj.key_results:
        slots.extend(_slots_for_kr(kr.title, kr.frequency, obj.title, anchor, horizon_end))

    return slots


def _slots_for_kr(
    kr_title: str,
    frequency: str,
    objective_title: str,
    anchor: datetime,
    horizon_end: datetime,
) -> list[SlotCandidate]:
    duration_min = _FREQUENCY_DURATION_MINUTES.get(frequency, 60)
    interval_days = _FREQUENCY_INTERVAL_DAYS.get(frequency, 7)

    block_start_hour = 10
    slots: list[SlotCandidate] = []

    if interval_days == 0:
        start = anchor.replace(hour=block_start_hour, minute=0, second=0, microsecond=0)
        if start < anchor:
            start += timedelta(days=1)
        if start <= horizon_end:
            slots.append(_make_slot(kr_title, objective_title, start, duration_min))
        return slots

    cursor = anchor.replace(hour=block_start_hour, minute=0, second=0, microsecond=0)
    while cursor <= horizon_end:
        slots.append(_make_slot(kr_title, objective_title, cursor, duration_min))
        cursor += timedelta(days=interval_days)

    return slots


def _make_slot(kr_title: str, objective_title: str, starts_at: datetime, duration_min: int) -> SlotCandidate:
    return SlotCandidate(
        title=kr_title,
        starts_at=starts_at,
        ends_at=starts_at + timedelta(minutes=duration_min),
        slot_type="work_block",
        notes=f"Scheduled work block for key result under '{objective_title}'",
        source_objective=objective_title,
        source_key_result=kr_title,
    )
