"""P2.2 / Epic 4.1 — Explainability helpers: human-readable reasons for task selection."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional


def get_task_reason(task, objective_title: Optional[str] = None) -> str:
    """Return a human-readable reason why this task is the next recommended action.

    Accepts either an ORM Task object or a dict with the same keys.
    Epic 4.1: enriched with deadline risk and ORM objective extraction.
    """
    today = date.today()

    # Normalise: support both ORM objects and plain dicts
    if isinstance(task, dict):
        due_raw = task.get("due_date")
        if isinstance(due_raw, str) and due_raw:
            try:
                due: Optional[date] = date.fromisoformat(due_raw)
            except ValueError:
                due = None
        elif isinstance(due_raw, date):
            due = due_raw
        else:
            due = None
        priority = task.get("priority")
        if not objective_title:
            objective_title = task.get("objective_title")
    else:
        due = task.due_date
        priority = task.priority
        # Epic 4.1: pull objective title from loaded ORM relations if not passed explicitly.
        # Use __dict__ to avoid triggering lazy-loads in async SQLAlchemy context (MissingGreenlet).
        if not objective_title:
            loaded = task.__dict__
            obj = loaded.get("objective")
            if obj:
                objective_title = obj.title
            else:
                kr = loaded.get("key_result")
                if kr is not None:
                    obj2 = kr.__dict__.get("objective")
                    if obj2:
                        objective_title = obj2.title

    if due and due < today:
        n = (today - due).days
        return f"Überfällig seit {n} {'Tag' if n == 1 else 'Tagen'}"
    if due and due == today:
        return "Heute fällig"
    # Epic 4.1: deadline risk — due within 2 days
    if due and due <= today + timedelta(days=2):
        days_left = (due - today).days
        return f"Fällig in {days_left} {'Tag' if days_left == 1 else 'Tagen'}"
    if priority == 1:
        return "Höchste Priorität"
    if objective_title:
        return f"Ziel: {objective_title}"
    return "Nächste offene Aufgabe"
