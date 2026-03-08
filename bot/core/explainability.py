"""P2.2 — Explainability helpers: human-readable reasons for task selection."""
from __future__ import annotations

from datetime import date
from typing import Optional


def get_task_reason(task, objective_title: Optional[str] = None) -> str:
    """Return a human-readable reason why this task is the next recommended action.

    Accepts either an ORM Task object or a dict with the same keys.
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
    else:
        due = task.due_date
        priority = task.priority

    if due and due < today:
        n = (today - due).days
        return f"Überfällig seit {n} {'Tag' if n == 1 else 'Tagen'}"
    if due and due == today:
        return "Heute fällig"
    if priority == 1:
        return "Höchste Priorität"
    if objective_title:
        return f"Ziel: {objective_title}"
    return "Nächste offene Aufgabe"
