"""Epic 2.2 — Free-slot planning with calendar awareness.

Pure, deterministic module (no DB access, no side-effects).

Algorithm overview:
1. Build occupied time ranges from today's calendar events.
2. Identify free windows in working hours (08:00–21:00).
3. Classify windows: tiny(<30), small(30-59), medium(60-119), large(≥120 min).
4. Tag windows adjacent to events as "near_meeting" (within 15 min).
5. Estimate task duration by priority when no explicit duration is available.
6. Score tasks per window: leverage (graph) + urgency (due date) + size fit.
7. Near-meeting windows prefer quick wins.
8. Assign best-fit task to each window (no double-booking tasks).
9. Annotate every suggested block with slot_reason + task_reason + confidence.

Anti-chaos guardrails:
- Max 5 suggested blocks per day.
- Never suggest blocks in the past.
- 15-minute buffer before the next event so blocks never bleed into meetings.
- Fallback mode (poor data) returns basic priority-ordered suggestions with
  confidence="low" and fallback=True.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Any, Optional


# ─── Constants ────────────────────────────────────────────────────────────────

WORK_START_HOUR = 8   # 08:00
WORK_END_HOUR = 21    # 21:00 (exclusive — last slot can start at 20:xx)
PRE_EVENT_BUFFER_MIN = 15   # minutes to keep free before a meeting
MAX_SUGGESTED_BLOCKS = 5
NEAR_MEETING_THRESHOLD_MIN = 15  # window is "near meeting" if this close

# Estimated task duration (minutes) by priority (1=highest, 5=lowest)
DURATION_BY_PRIORITY: dict[int, int] = {
    1: 90,
    2: 60,
    3: 45,
    4: 30,
    5: 15,
}

# Window types by duration
WINDOW_TYPE_TINY = "tiny"       # < 30 min  → skip suggestions
WINDOW_TYPE_SMALL = "small"     # 30–59 min → quick wins, P4/P5
WINDOW_TYPE_MEDIUM = "medium"   # 60–119 min → focused, P2/P3
WINDOW_TYPE_LARGE = "large"     # ≥ 120 min → deep work, P1/P2


# ─── Data classes ─────────────────────────────────────────────────────────────

@dataclass
class TimeRange:
    start: int  # minutes from midnight
    end: int    # minutes from midnight (exclusive)

    @property
    def duration_min(self) -> int:
        return max(0, self.end - self.start)

    def overlaps(self, other: "TimeRange") -> bool:
        return self.start < other.end and other.start < self.end


@dataclass
class FreeWindow:
    start_min: int   # minutes from midnight
    end_min: int     # minutes from midnight
    window_type: str
    is_near_meeting: bool
    is_past: bool

    @property
    def duration_min(self) -> int:
        return max(0, self.end_min - self.start_min)

    @property
    def start_hhmm(self) -> str:
        return _min_to_hhmm(self.start_min)

    @property
    def end_hhmm(self) -> str:
        return _min_to_hhmm(self.end_min)


@dataclass
class SuggestedBlock:
    start_time: str         # "HH:MM"
    end_time: str           # "HH:MM"
    duration_minutes: int
    window_type: str
    is_near_meeting: bool
    task_id: Optional[int]
    task_title: Optional[str]
    task_priority: Optional[int]
    estimated_minutes: int
    slot_reason: str
    task_reason: str
    confidence: str         # "high" | "medium" | "low"
    linked_task_id: Optional[int] = None  # backward-compat alias for task_id


@dataclass
class FreeSlotPlan:
    windows: list[dict]
    suggested_blocks: list[dict]
    free_minutes_total: int
    free_minutes_used: int
    fallback: bool
    data_quality: str  # "good" | "no_events" | "no_tasks" | "poor"


# ─── Public API ───────────────────────────────────────────────────────────────

def plan_free_slots(
    events: list[Any],
    tasks: list[Any],
    today: date,
    now_dt: Optional[datetime] = None,
    graph_data: Optional[dict[int, dict]] = None,
) -> FreeSlotPlan:
    """Return a FreeSlotPlan for the given day.

    Args:
        events:     CalendarEvent ORM objects (or dicts) for today.
        tasks:      Task ORM objects (open, non-shopping) sorted by priority.
        today:      The date being planned.
        now_dt:     Current datetime; blocks in the past are skipped.
        graph_data: Optional dict mapping task_id → {unlocks_count, contributes_to}.
                    When provided, high-leverage tasks get priority in larger slots.
    """
    now_min = _dt_to_min(now_dt) if now_dt else WORK_START_HOUR * 60
    graph = graph_data or {}

    # ── 1. Build occupied ranges from events ──────────────────────────────────
    occupied: list[TimeRange] = []
    event_starts: list[int] = []  # for near-meeting detection
    for ev in events:
        if _event_all_day(ev):
            continue
        s = _event_start_min(ev)
        e = _event_end_min(ev)
        if e is None:
            e = s + 60  # assume 1h if no end_time
        occupied.append(TimeRange(s, e))
        event_starts.append(s)

    occupied.sort(key=lambda r: r.start)

    # ── 2. Merge overlapping occupied ranges ──────────────────────────────────
    merged: list[TimeRange] = _merge_ranges(occupied)

    # ── 3. Find free windows within working hours ─────────────────────────────
    work_start = WORK_START_HOUR * 60
    work_end = WORK_END_HOUR * 60

    windows: list[FreeWindow] = _find_free_windows(
        merged, work_start, work_end, now_min, event_starts
    )

    # ── 4. Score and assign tasks to windows ──────────────────────────────────
    actionable_windows = [w for w in windows if w.window_type != WINDOW_TYPE_TINY]

    data_quality: str
    if not events:
        data_quality = "no_events"
    elif not tasks:
        data_quality = "no_tasks"
    elif not actionable_windows:
        data_quality = "poor"
    else:
        data_quality = "good"

    fallback = data_quality in ("poor", "no_events")

    suggested_blocks: list[SuggestedBlock] = []
    used_task_ids: set[int] = set()

    if tasks and actionable_windows:
        suggested_blocks = _assign_tasks_to_windows(
            actionable_windows, tasks, today, now_min, graph, used_task_ids
        )
    elif tasks and fallback:
        # Fallback: no usable windows — suggest top tasks with no slot info
        suggested_blocks = _fallback_suggestions(tasks, today, graph)

    free_total = sum(w.duration_min for w in windows)
    free_used = sum(b.duration_minutes for b in suggested_blocks)

    return {
        "windows": [_window_to_dict(w) for w in windows],
        "suggested_blocks": [_block_to_dict(b) for b in suggested_blocks],
        "free_minutes_total": free_total,
        "free_minutes_used": free_used,
        "fallback": fallback,
        "data_quality": data_quality,
    }


# ─── Window detection ─────────────────────────────────────────────────────────

def _find_free_windows(
    occupied: list[TimeRange],
    work_start: int,
    work_end: int,
    now_min: int,
    event_starts: list[int],
) -> list[FreeWindow]:
    """Return free windows as gaps between occupied ranges inside working hours."""
    # Build timeline of occupied minutes, clamped to work hours
    gaps: list[tuple[int, int]] = []
    cursor = work_start

    for r in occupied:
        gap_start = max(cursor, work_start)
        gap_end = min(r.start, work_end)
        if gap_end > gap_start:
            gaps.append((gap_start, gap_end))
        cursor = max(cursor, r.end)

    # Trailing gap after last event
    if cursor < work_end:
        gaps.append((cursor, work_end))

    # If no events at all, whole working day is free
    if not occupied:
        gaps = [(work_start, work_end)]

    windows: list[FreeWindow] = []
    for start, end in gaps:
        dur = end - start
        is_past = end <= now_min
        is_near = _is_near_meeting(start, end, event_starts)
        wtype = _classify_window(dur)
        windows.append(FreeWindow(
            start_min=start,
            end_min=end,
            window_type=wtype,
            is_near_meeting=is_near,
            is_past=is_past,
        ))

    return windows


def _classify_window(dur_min: int) -> str:
    if dur_min < 30:
        return WINDOW_TYPE_TINY
    if dur_min < 60:
        return WINDOW_TYPE_SMALL
    if dur_min < 120:
        return WINDOW_TYPE_MEDIUM
    return WINDOW_TYPE_LARGE


def _is_near_meeting(start: int, end: int, event_starts: list[int]) -> bool:
    """True if this window is within NEAR_MEETING_THRESHOLD_MIN of any event."""
    for es in event_starts:
        if abs(es - end) <= NEAR_MEETING_THRESHOLD_MIN:
            return True
        if abs(start - es) <= NEAR_MEETING_THRESHOLD_MIN:
            return True
    return False


# ─── Task assignment ──────────────────────────────────────────────────────────

def _assign_tasks_to_windows(
    windows: list[FreeWindow],
    tasks: list[Any],
    today: date,
    now_min: int,
    graph: dict[int, dict],
    used_task_ids: set[int],
) -> list[SuggestedBlock]:
    blocks: list[SuggestedBlock] = []

    # Sort windows: future first, then by start time
    future_windows = [w for w in windows if not w.is_past]
    future_windows.sort(key=lambda w: w.start_min)

    for window in future_windows:
        if len(blocks) >= MAX_SUGGESTED_BLOCKS:
            break
        if window.window_type == WINDOW_TYPE_TINY:
            continue

        best = _pick_best_task(window, tasks, today, graph, used_task_ids)
        if best is None:
            continue

        task_id = _task_id(best)
        used_task_ids.add(task_id)

        est_min = DURATION_BY_PRIORITY.get(_task_priority(best), 45)
        # Clamp to available window minus pre-event buffer
        usable = window.duration_min - PRE_EVENT_BUFFER_MIN
        actual_min = min(est_min, usable)
        actual_min = max(actual_min, 15)  # at least 15 min

        block_start = window.start_min
        block_end = block_start + actual_min

        slot_reason = _build_slot_reason(window)
        task_reason = _build_task_reason(best, today, graph)
        confidence = _compute_confidence(window, best, graph)

        blocks.append(SuggestedBlock(
            start_time=_min_to_hhmm(block_start),
            end_time=_min_to_hhmm(block_end),
            duration_minutes=actual_min,
            window_type=window.window_type,
            is_near_meeting=window.is_near_meeting,
            task_id=task_id,
            task_title=_task_title(best),
            task_priority=_task_priority(best),
            estimated_minutes=est_min,
            slot_reason=slot_reason,
            task_reason=task_reason,
            confidence=confidence,
            linked_task_id=task_id,  # backward-compat
        ))

    return blocks


def _pick_best_task(
    window: FreeWindow,
    tasks: list[Any],
    today: date,
    graph: dict[int, dict],
    used_task_ids: set[int],
) -> Any:
    """Score each unused task for this window and return the best fit."""
    best_task = None
    best_score = -1

    for task in tasks:
        tid = _task_id(task)
        if tid in used_task_ids:
            continue

        est_min = DURATION_BY_PRIORITY.get(_task_priority(task), 45)
        usable_min = window.duration_min - PRE_EVENT_BUFFER_MIN

        # Hard filter: task must fit with at least 15 min to spare
        if est_min > usable_min + 15:
            # For near-meeting windows, prefer shorter tasks → also skip if too long
            if window.is_near_meeting and est_min > usable_min:
                continue
            elif not window.is_near_meeting:
                continue

        score = _score_task_for_window(task, window, today, graph)
        if score > best_score:
            best_score = score
            best_task = task

    return best_task


def _score_task_for_window(
    task: Any,
    window: FreeWindow,
    today: date,
    graph: dict[int, dict],
) -> int:
    score = 0

    # Priority score (P1=50, P5=10)
    priority = _task_priority(task)
    score += (6 - priority) * 10

    # Urgency
    due = _task_due_date(task)
    if due:
        if due < today:
            score += 40  # overdue
        elif due == today:
            score += 30  # due today
        elif due <= today + timedelta(days=2):
            score += 20
        elif due <= today + timedelta(days=7):
            score += 10

    # Graph leverage (Epic 1.2 data)
    tid = _task_id(task)
    gdata = graph.get(tid, {})
    unlocks = gdata.get("unlocks_count", 0) or 0
    contributes = len(gdata.get("contributes_to", []) or [])
    score += unlocks * 10
    score += contributes * 5

    # Window fit bonus
    est_min = DURATION_BY_PRIORITY.get(priority, 45)
    if window.window_type == WINDOW_TYPE_LARGE and priority <= 2:
        score += 15  # deep work gets large windows
    elif window.window_type == WINDOW_TYPE_MEDIUM and 2 <= priority <= 3:
        score += 10
    elif window.window_type == WINDOW_TYPE_SMALL and priority >= 4:
        score += 10  # quick wins fit small windows

    # Near-meeting: boost fast tasks
    if window.is_near_meeting and est_min <= 30:
        score += 20
    elif window.is_near_meeting and est_min > 60:
        score -= 10  # penalise long tasks near meetings

    return score


# ─── Fallback ─────────────────────────────────────────────────────────────────

def _fallback_suggestions(
    tasks: list[Any],
    today: date,
    graph: dict[int, dict],
) -> list[SuggestedBlock]:
    """When no free windows found: return top tasks with no time slot (low conf)."""
    blocks: list[SuggestedBlock] = []
    for task in tasks[:MAX_SUGGESTED_BLOCKS]:
        tid = _task_id(task)
        est_min = DURATION_BY_PRIORITY.get(_task_priority(task), 45)
        task_reason = _build_task_reason(task, today, graph)
        blocks.append(SuggestedBlock(
            start_time="—",
            end_time="—",
            duration_minutes=est_min,
            window_type="unknown",
            is_near_meeting=False,
            task_id=tid,
            task_title=_task_title(task),
            task_priority=_task_priority(task),
            estimated_minutes=est_min,
            slot_reason="No calendar data — schedule manually",
            task_reason=task_reason,
            confidence="low",
            linked_task_id=tid,
        ))
    return blocks


# ─── Reason builders ──────────────────────────────────────────────────────────

def _build_slot_reason(window: FreeWindow) -> str:
    parts: list[str] = []
    if window.window_type == WINDOW_TYPE_LARGE:
        parts.append("Large window ideal for deep/focused work")
    elif window.window_type == WINDOW_TYPE_MEDIUM:
        parts.append("Medium window fits a focused task")
    elif window.window_type == WINDOW_TYPE_SMALL:
        parts.append("Short window — good for a quick win")
    if window.is_near_meeting:
        parts.append("near a meeting")
    return ", ".join(parts) if parts else "Free window available"


def _build_task_reason(task: Any, today: date, graph: dict[int, dict]) -> str:
    reasons: list[str] = []
    due = _task_due_date(task)
    if due:
        if due < today:
            reasons.append("overdue")
        elif due == today:
            reasons.append("due today")
        elif due <= today + timedelta(days=2):
            reasons.append("due in 2 days")
        elif due <= today + timedelta(days=7):
            reasons.append("due this week")

    tid = _task_id(task)
    gdata = graph.get(tid, {})
    unlocks = gdata.get("unlocks_count", 0) or 0
    contributes = gdata.get("contributes_to") or []
    if unlocks:
        reasons.append(f"unlocks {unlocks} task{'s' if unlocks != 1 else ''}")
    if contributes:
        reasons.append(f"contributes to {len(contributes)} objective{'s' if len(contributes) != 1 else ''}")

    priority = _task_priority(task)
    if priority == 1:
        reasons.append("highest priority")
    elif priority == 2:
        reasons.append("high priority")

    return ", ".join(reasons) if reasons else "next open task"


def _compute_confidence(window: FreeWindow, task: Any, graph: dict[int, dict]) -> str:
    tid = _task_id(task)
    has_graph = bool(graph.get(tid))
    priority = _task_priority(task)
    due = _task_due_date(task)
    has_urgency = due is not None
    if has_graph and (has_urgency or priority <= 2):
        return "high"
    if has_graph or has_urgency or priority <= 2:
        return "medium"
    return "low"


# ─── Serialisation helpers ────────────────────────────────────────────────────

def _window_to_dict(w: FreeWindow) -> dict:
    return {
        "start_time": w.start_hhmm,
        "end_time": w.end_hhmm,
        "window_minutes": w.duration_min,
        "window_type": w.window_type,
        "is_near_meeting": w.is_near_meeting,
        "is_past": w.is_past,
    }


def _block_to_dict(b: SuggestedBlock) -> dict:
    return {
        "start_time": b.start_time,
        "end_time": b.end_time,
        "duration_minutes": b.duration_minutes,
        "window_type": b.window_type,
        "is_near_meeting": b.is_near_meeting,
        "task_id": b.task_id,
        "task_title": b.task_title,
        "task_priority": b.task_priority,
        "estimated_minutes": b.estimated_minutes,
        "slot_reason": b.slot_reason,
        "task_reason": b.task_reason,
        "confidence": b.confidence,
        "linked_task_id": b.linked_task_id,
    }


# ─── Utility helpers ──────────────────────────────────────────────────────────

def _min_to_hhmm(minutes: int) -> str:
    h, m = divmod(max(0, minutes), 60)
    return f"{min(h, 23):02d}:{m:02d}"


def _dt_to_min(dt: datetime) -> int:
    return dt.hour * 60 + dt.minute


def _merge_ranges(ranges: list[TimeRange]) -> list[TimeRange]:
    if not ranges:
        return []
    merged: list[TimeRange] = [TimeRange(ranges[0].start, ranges[0].end)]
    for r in ranges[1:]:
        last = merged[-1]
        if r.start <= last.end:
            merged[-1] = TimeRange(last.start, max(last.end, r.end))
        else:
            merged.append(TimeRange(r.start, r.end))
    return merged


# ─── ORM field accessors (duck-typed for both ORM objects and dicts) ──────────

def _attr(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _event_all_day(ev: Any) -> bool:
    return bool(_attr(ev, "all_day", False))


def _event_start_min(ev: Any) -> int:
    st = _attr(ev, "start_time")
    if isinstance(st, datetime):
        return st.hour * 60 + st.minute
    if isinstance(st, str):
        try:
            dt = datetime.fromisoformat(st)
            return dt.hour * 60 + dt.minute
        except ValueError:
            pass
    return WORK_START_HOUR * 60


def _event_end_min(ev: Any) -> Optional[int]:
    et = _attr(ev, "end_time")
    if isinstance(et, datetime):
        return et.hour * 60 + et.minute
    if isinstance(et, str):
        try:
            dt = datetime.fromisoformat(et)
            return dt.hour * 60 + dt.minute
        except ValueError:
            pass
    return None


def _task_id(task: Any) -> int:
    return int(_attr(task, "id", 0))


def _task_priority(task: Any) -> int:
    p = _attr(task, "priority", 3)
    try:
        return int(p)
    except (TypeError, ValueError):
        return 3


def _task_due_date(task: Any) -> Optional[date]:
    d = _attr(task, "due_date")
    if isinstance(d, date):
        return d
    if isinstance(d, str) and d:
        try:
            return date.fromisoformat(d)
        except ValueError:
            pass
    return None


def _task_title(task: Any) -> str:
    return str(_attr(task, "title", ""))
