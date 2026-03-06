"""CORE-3d: Pure conflict-detection helper for slot candidates (read-only, no side-effects)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from bot.core.slot_candidates import SlotCandidate


@dataclass
class ConflictInfo:
    event_id: int
    title: str
    starts_at: datetime
    ends_at: datetime


@dataclass
class CandidateWithConflicts:
    candidate: SlotCandidate
    conflicts: list[ConflictInfo] = field(default_factory=list)

    @property
    def has_conflict(self) -> bool:
        return bool(self.conflicts)


def _event_end(event_start: datetime, event_end: datetime | None) -> datetime:
    return event_end if event_end is not None else event_start + timedelta(hours=1)


def _overlaps(a_start: datetime, a_end: datetime, b_start: datetime, b_end: datetime) -> bool:
    return a_start < b_end and b_start < a_end


def detect_conflicts(candidates: list[SlotCandidate], existing_events: list) -> list[CandidateWithConflicts]:
    """Annotate each slot candidate with any overlapping existing calendar events."""
    results: list[CandidateWithConflicts] = []
    for candidate in candidates:
        conflicts: list[ConflictInfo] = []
        for ev in existing_events:
            ev_end = _event_end(ev.start_time, ev.end_time)
            if _overlaps(candidate.starts_at, candidate.ends_at, ev.start_time, ev_end):
                conflicts.append(
                    ConflictInfo(
                        event_id=ev.id,
                        title=ev.title,
                        starts_at=ev.start_time,
                        ends_at=ev_end,
                    )
                )
        results.append(CandidateWithConflicts(candidate=candidate, conflicts=conflicts))
    return results
