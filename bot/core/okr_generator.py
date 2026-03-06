"""CORE-1a: OKR draft models + deterministic fallback generator.

Read-only utility module (no DB writes, no external API calls).
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Optional

from pydantic import BaseModel, Field


class DraftKeyResult(BaseModel):
    title: str
    metric_type: str = "boolean"  # boolean | numeric | percentage
    target_value: Optional[float] = None
    unit: Optional[str] = None
    frequency: str = "weekly"  # daily | weekly | monthly | once


class DraftObjective(BaseModel):
    title: str
    category: str = "general"
    description: Optional[str] = None
    target_date: Optional[date] = None
    key_results: list[DraftKeyResult] = Field(default_factory=list)


class OKRDraft(BaseModel):
    objectives: list[DraftObjective]
    source_text: str
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    is_fallback: bool = True


_CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "health": ["sport", "fitness", "training", "gym", "workout", "health", "gesundheit"],
    "work": ["arbeit", "job", "career", "project", "projekt", "business", "startup", "product"],
    "learning": ["lernen", "learn", "study", "kurs", "course", "skill", "buch", "book"],
    "finance": ["geld", "money", "save", "sparen", "budget", "income", "expense", "invest"],
    "relationships": ["friends", "freunde", "family", "familie", "relationship", "netzwerk"],
}


def _detect_category(text: str) -> str:
    lower = text.lower()
    scores = {cat: sum(1 for kw in kws if kw in lower) for cat, kws in _CATEGORY_KEYWORDS.items()}
    best = max(scores, key=lambda c: scores[c])
    return best if scores[best] > 0 else "general"


def _split_goals(text: str) -> list[str]:
    numbered = re.split(r"(?:^|\n)\s*\d+[.)]\s+", text.strip())
    numbered = [g.strip() for g in numbered if g.strip()]
    if len(numbered) >= 2:
        return numbered[:3]

    bulleted = re.split(r"(?:^|\n)\s*[-•*]\s+", text.strip())
    bulleted = [g.strip() for g in bulleted if g.strip()]
    if len(bulleted) >= 2:
        return bulleted[:3]

    by_line = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if len(by_line) >= 2:
        return by_line[:3]

    return [text.strip()] if text.strip() else []


def _default_krs_for_category(category: str, objective_title: str) -> list[DraftKeyResult]:
    if category == "health":
        return [
            DraftKeyResult(title=f"Track progress on: {objective_title}", metric_type="numeric", target_value=4.0, unit="sessions"),
            DraftKeyResult(title="Weekly check-in completed", metric_type="boolean"),
        ]
    if category == "work":
        return [
            DraftKeyResult(title=f"Milestone reached: {objective_title}", metric_type="boolean"),
            DraftKeyResult(title="Dedicated focus hours logged", metric_type="numeric", target_value=10.0, unit="hours"),
        ]
    if category == "learning":
        return [
            DraftKeyResult(title=f"Study sessions completed for: {objective_title}", metric_type="numeric", target_value=3.0, unit="sessions"),
            DraftKeyResult(title="Key takeaway documented", metric_type="boolean"),
        ]
    if category == "finance":
        return [
            DraftKeyResult(title=f"Action taken on: {objective_title}", metric_type="boolean"),
            DraftKeyResult(title="Budget / progress reviewed", metric_type="boolean"),
        ]
    if category == "relationships":
        return [
            DraftKeyResult(title=f"Meaningful interaction: {objective_title}", metric_type="numeric", target_value=1.0, unit="interactions"),
            DraftKeyResult(title="Follow-up or plan made", metric_type="boolean"),
        ]
    return [
        DraftKeyResult(title=f"Weekly action completed: {objective_title}", metric_type="boolean"),
        DraftKeyResult(title="Mid-point review done", metric_type="boolean"),
    ]


def generate_okr_draft_fallback(source_text: str, horizon_weeks: int = 4) -> OKRDraft:
    """Build deterministic OKR draft from free-form goal text.

    - Up to 3 objectives
    - Category detection per objective
    - 2 default key results per objective
    """
    if not source_text or not source_text.strip():
        return OKRDraft(objectives=[], source_text=source_text)

    goal_strings = _split_goals(source_text)
    if not goal_strings:
        return OKRDraft(objectives=[], source_text=source_text)

    target_date = date.today() + timedelta(weeks=horizon_weeks)
    objectives: list[DraftObjective] = []

    for goal in goal_strings:
        title = goal if len(goal) <= 120 else goal[:117].rsplit(" ", 1)[0] + "..."
        category = _detect_category(title)
        krs = _default_krs_for_category(category, title)
        objectives.append(
            DraftObjective(
                title=title,
                category=category,
                target_date=target_date,
                key_results=krs,
            )
        )

    return OKRDraft(objectives=objectives, source_text=source_text, is_fallback=True)
