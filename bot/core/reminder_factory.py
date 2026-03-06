"""CORE-4a: Pure reminder draft factory (read-only, no side-effects).

Generates reminder drafts from an accepted OKR proposal without scheduling anything
or writing to the database. Anti-spam constraints (quiet hours, max per day,
min interval between reminders) are encoded in ReminderConfig.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

from pydantic import BaseModel, Field

from bot.core.okr_generator import DraftKeyResult, OKRDraft


class ReminderConfig(BaseModel):
    """Anti-spam constraints for reminder generation. All fields have safe defaults."""

    quiet_hour_start: int = Field(22, ge=0, le=23, description="Start of quiet hours (24h, inclusive)")
    quiet_hour_end: int = Field(8, ge=0, le=23, description="End of quiet hours (24h, exclusive)")
    max_per_day: int = Field(3, ge=1, le=10, description="Max reminders scheduled on any single day")
    min_interval_hours: int = Field(4, ge=1, le=24, description="Min hours between consecutive reminders")
    preferred_hour: int = Field(9, ge=0, le=23, description="Preferred hour-of-day for reminder delivery")
    horizon_days: int = Field(30, ge=1, le=90, description="How many days ahead to generate reminders")


class ReminderDraft(BaseModel):
    """A single proposed reminder — not persisted, causes no side-effects."""

    title: str
    body: str
    scheduled_at: datetime
    source_objective: str
    source_key_result: str
    frequency: str  # daily | weekly | monthly | once
    anti_spam_adjusted: bool = False  # True if timing was shifted out of quiet hours


_FREQUENCY_INTERVAL_DAYS: dict[str, int] = {
    "daily": 1,
    "weekly": 7,
    "monthly": 30,
    "once": 0,
}


def generate_reminder_drafts(
    draft_payload: dict[str, Any],
    config: ReminderConfig | None = None,
    anchor: datetime | None = None,
) -> list[ReminderDraft]:
    """Generate reminder drafts from an OKR draft payload.

    Pure function — no I/O, no DB writes, no scheduling side-effects.
    Anti-spam guardrails (quiet hours, max_per_day, min_interval) are applied in-memory.

    Args:
        draft_payload: Raw dict matching the OKRDraft schema.
        config: Anti-spam constraints; safe defaults are used if not provided.
        anchor: Start of the generation window; defaults to utcnow().

    Returns:
        Sorted list of ReminderDraft instances within the configured horizon.
    """
    if config is None:
        config = ReminderConfig()
    if anchor is None:
        anchor = datetime.utcnow()

    try:
        draft = OKRDraft.model_validate(draft_payload)
    except Exception:
        return []

    horizon_end = anchor + timedelta(days=config.horizon_days)

    raw: list[ReminderDraft] = []
    for obj in draft.objectives:
        for kr in obj.key_results:
            raw.extend(_reminders_for_kr(kr, obj.title, anchor, horizon_end, config))

    raw.sort(key=lambda r: r.scheduled_at)
    return _apply_anti_spam(raw, config)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _is_in_quiet_hours(dt: datetime, config: ReminderConfig) -> bool:
    h = dt.hour
    if config.quiet_hour_start > config.quiet_hour_end:
        # Window spans midnight (e.g. 22:00 → 08:00)
        return h >= config.quiet_hour_start or h < config.quiet_hour_end
    return config.quiet_hour_start <= h < config.quiet_hour_end


def _shift_out_of_quiet(dt: datetime, config: ReminderConfig) -> tuple[datetime, bool]:
    """Advance dt to the next non-quiet hour if needed.

    Returns (adjusted_dt, was_adjusted).
    """
    if not _is_in_quiet_hours(dt, config):
        return dt, False
    candidate = dt.replace(hour=config.quiet_hour_end, minute=0, second=0, microsecond=0)
    if candidate <= dt:
        candidate += timedelta(days=1)
    return candidate, True


def _reminders_for_kr(
    kr: DraftKeyResult,
    objective_title: str,
    anchor: datetime,
    horizon_end: datetime,
    config: ReminderConfig,
) -> list[ReminderDraft]:
    interval_days = _FREQUENCY_INTERVAL_DAYS.get(kr.frequency, 7)
    base = anchor.replace(hour=config.preferred_hour, minute=0, second=0, microsecond=0)
    if base < anchor:
        base += timedelta(days=1)

    drafts: list[ReminderDraft] = []

    if interval_days == 0:
        # once — single reminder
        scheduled, adjusted = _shift_out_of_quiet(base, config)
        if scheduled <= horizon_end:
            drafts.append(_make_draft(kr, objective_title, scheduled, adjusted))
        return drafts

    cursor = base
    while cursor <= horizon_end:
        scheduled, adjusted = _shift_out_of_quiet(cursor, config)
        if scheduled <= horizon_end:
            drafts.append(_make_draft(kr, objective_title, scheduled, adjusted))
        cursor += timedelta(days=interval_days)

    return drafts


def _make_draft(
    kr: DraftKeyResult,
    objective_title: str,
    scheduled_at: datetime,
    anti_spam_adjusted: bool,
) -> ReminderDraft:
    metric_hint = ""
    if kr.metric_type == "numeric" and kr.target_value is not None:
        unit = kr.unit or "units"
        metric_hint = f" (target: {kr.target_value} {unit})"

    return ReminderDraft(
        title=f"Reminder: {kr.title}",
        body=f"Time to work on '{objective_title}'. KR: {kr.title}{metric_hint}.",
        scheduled_at=scheduled_at,
        source_objective=objective_title,
        source_key_result=kr.title,
        frequency=kr.frequency,
        anti_spam_adjusted=anti_spam_adjusted,
    )


def _apply_anti_spam(drafts: list[ReminderDraft], config: ReminderConfig) -> list[ReminderDraft]:
    """Enforce max_per_day and min_interval_hours across all drafted reminders."""
    day_counts: dict[str, int] = defaultdict(int)
    last_scheduled: datetime | None = None
    result: list[ReminderDraft] = []

    for draft in drafts:
        day_key = draft.scheduled_at.date().isoformat()

        if day_counts[day_key] >= config.max_per_day:
            continue

        if last_scheduled is not None:
            gap_hours = (draft.scheduled_at - last_scheduled).total_seconds() / 3600
            if gap_hours < config.min_interval_hours:
                continue

        result.append(draft)
        day_counts[day_key] += 1
        last_scheduled = draft.scheduled_at

    return result
