"""CORE-4a/4b: Pure reminder draft factory (read-only, no side-effects).

Generates reminder drafts from an accepted OKR proposal without scheduling anything
or writing to the database. Supports three reminder kinds:
  - daily_checkin: morning check-in prompt (generated once per day in horizon)
  - weekly_review: end-of-week review prompt (generated once per week on Sundays)
  - kr_cadence: per-KR frequency-driven reminders derived from OKR draft KRs

Anti-spam constraints (quiet hours, max per day, min interval between reminders)
are encoded in ReminderConfig and applied as pure in-memory filters.
"""

from __future__ import annotations

import enum
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Optional

from pydantic import BaseModel, Field

from bot.core.okr_generator import DraftKeyResult, OKRDraft


class ReminderKind(str, enum.Enum):
    daily_checkin = "daily_checkin"
    weekly_review = "weekly_review"
    kr_cadence = "kr_cadence"


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

    kind: ReminderKind
    title: str
    body: str
    scheduled_at: datetime
    scheduled_time_local: Optional[str] = None  # "HH:MM" local time representation
    cron: Optional[str] = None  # cron expression for recurring reminders
    priority: int = Field(2, ge=1, le=3)  # 1=high, 2=medium, 3=low
    quiet_hours_respected: bool = True  # True if final scheduled time is outside quiet hours
    max_per_day_bucket: str = ""  # date-key used for per-day anti-spam counting
    source_objective: Optional[str] = None
    source_key_result: Optional[str] = None
    frequency: str  # daily | weekly | monthly | once
    anti_spam_adjusted: bool = False  # True if timing was shifted out of quiet hours


_FREQUENCY_INTERVAL_DAYS: dict[str, int] = {
    "daily": 1,
    "weekly": 7,
    "monthly": 30,
    "once": 0,
}

_FREQUENCY_CRON: dict[str, str] = {
    "daily": "0 {hour} * * *",
    "weekly": "0 {hour} * * 1",
    "monthly": "0 {hour} 1 * *",
}

_FREQUENCY_PRIORITY: dict[str, int] = {
    "daily": 1,
    "weekly": 2,
    "monthly": 3,
    "once": 2,
}


def generate_reminder_drafts(
    draft_payload: dict[str, Any],
    config: ReminderConfig | None = None,
    anchor: datetime | None = None,
) -> list[ReminderDraft]:
    """Generate reminder drafts from an OKR draft payload.

    Pure function — no I/O, no DB writes, no scheduling side-effects.
    Anti-spam guardrails (quiet hours, max_per_day, min_interval) are applied in-memory.
    Produces three reminder kinds: daily_checkin, weekly_review, and kr_cadence.

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

    # System-level reminder types (independent of individual KRs)
    raw.extend(_daily_checkin_reminders(anchor, horizon_end, config))
    raw.extend(_weekly_review_reminders(anchor, horizon_end, config))

    # KR-cadence reminders derived from the OKR draft
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


def _make_cron(frequency: str, hour: int) -> Optional[str]:
    template = _FREQUENCY_CRON.get(frequency)
    if template is None:
        return None
    return template.format(hour=hour)


def _daily_checkin_reminders(
    anchor: datetime,
    horizon_end: datetime,
    config: ReminderConfig,
) -> list[ReminderDraft]:
    """One daily check-in reminder per day in the horizon."""
    base = anchor.replace(hour=config.preferred_hour, minute=0, second=0, microsecond=0)
    if base < anchor:
        base += timedelta(days=1)

    cron = f"0 {config.preferred_hour} * * *"
    drafts: list[ReminderDraft] = []
    cursor = base
    while cursor <= horizon_end:
        scheduled, adjusted = _shift_out_of_quiet(cursor, config)
        if scheduled <= horizon_end:
            drafts.append(
                ReminderDraft(
                    kind=ReminderKind.daily_checkin,
                    title="Daily Check-in",
                    body="Good morning! Take a moment to review your priorities and set intentions for today.",
                    scheduled_at=scheduled,
                    scheduled_time_local=scheduled.strftime("%H:%M"),
                    cron=cron,
                    priority=1,
                    quiet_hours_respected=not adjusted,
                    max_per_day_bucket=scheduled.date().isoformat(),
                    source_objective=None,
                    source_key_result=None,
                    frequency="daily",
                    anti_spam_adjusted=adjusted,
                )
            )
        cursor += timedelta(days=1)
    return drafts


def _weekly_review_reminders(
    anchor: datetime,
    horizon_end: datetime,
    config: ReminderConfig,
) -> list[ReminderDraft]:
    """One weekly review reminder per week (Sunday) in the horizon."""
    # weekday(): Mon=0 … Sun=6; find the next Sunday strictly after anchor
    days_until_sunday = (6 - anchor.weekday()) % 7
    base = anchor.replace(hour=config.preferred_hour, minute=0, second=0, microsecond=0)
    base += timedelta(days=days_until_sunday if days_until_sunday > 0 else 7)

    cron = f"0 {config.preferred_hour} * * 0"
    drafts: list[ReminderDraft] = []
    cursor = base
    while cursor <= horizon_end:
        scheduled, adjusted = _shift_out_of_quiet(cursor, config)
        if scheduled <= horizon_end:
            drafts.append(
                ReminderDraft(
                    kind=ReminderKind.weekly_review,
                    title="Weekly Review",
                    body="Time for your weekly review! Reflect on progress, celebrate wins, and plan the week ahead.",
                    scheduled_at=scheduled,
                    scheduled_time_local=scheduled.strftime("%H:%M"),
                    cron=cron,
                    priority=1,
                    quiet_hours_respected=not adjusted,
                    max_per_day_bucket=scheduled.date().isoformat(),
                    source_objective=None,
                    source_key_result=None,
                    frequency="weekly",
                    anti_spam_adjusted=adjusted,
                )
            )
        cursor += timedelta(days=7)
    return drafts


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

    priority = _FREQUENCY_PRIORITY.get(kr.frequency, 2)
    cron = _make_cron(kr.frequency, config.preferred_hour)
    drafts: list[ReminderDraft] = []

    if interval_days == 0:
        # once — single reminder
        scheduled, adjusted = _shift_out_of_quiet(base, config)
        if scheduled <= horizon_end:
            drafts.append(_make_kr_draft(kr, objective_title, scheduled, adjusted, priority, cron))
        return drafts

    cursor = base
    while cursor <= horizon_end:
        scheduled, adjusted = _shift_out_of_quiet(cursor, config)
        if scheduled <= horizon_end:
            drafts.append(_make_kr_draft(kr, objective_title, scheduled, adjusted, priority, cron))
        cursor += timedelta(days=interval_days)

    return drafts


def _make_kr_draft(
    kr: DraftKeyResult,
    objective_title: str,
    scheduled_at: datetime,
    anti_spam_adjusted: bool,
    priority: int,
    cron: Optional[str],
) -> ReminderDraft:
    metric_hint = ""
    if kr.metric_type == "numeric" and kr.target_value is not None:
        unit = kr.unit or "units"
        metric_hint = f" (target: {kr.target_value} {unit})"

    return ReminderDraft(
        kind=ReminderKind.kr_cadence,
        title=f"Reminder: {kr.title}",
        body=f"Time to work on '{objective_title}'. KR: {kr.title}{metric_hint}.",
        scheduled_at=scheduled_at,
        scheduled_time_local=scheduled_at.strftime("%H:%M"),
        cron=cron,
        priority=priority,
        quiet_hours_respected=not anti_spam_adjusted,
        max_per_day_bucket=scheduled_at.date().isoformat(),
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
        day_key = draft.max_per_day_bucket or draft.scheduled_at.date().isoformat()

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
