"""Config-driven fitness split helper (3er rotation)."""
from __future__ import annotations

from datetime import date, datetime
import json
from pathlib import Path
from typing import Any

DEFAULT_FITNESS_PROTOCOL_PATH = (
    Path(__file__).resolve().parents[2] / "docs" / "protocols" / "lukas_fitness_split.json"
)


def load_fitness_protocol(path: Path | str | None = None) -> dict[str, Any]:
    protocol_path = Path(path) if path else DEFAULT_FITNESS_PROTOCOL_PATH
    with protocol_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def get_today_split(protocol: dict[str, Any], target_date: date | None = None) -> dict[str, Any]:
    now = target_date or date.today()
    meta = protocol.get("meta", {})
    anchor = datetime.strptime(meta.get("rotation_anchor_date", "2026-01-01"), "%Y-%m-%d").date()
    rotation: list[str] = meta.get("rotation", ["Beine", "Pull", "Push"])
    rest_days: list[int] = meta.get("rest_days", [])

    weekday = now.weekday()  # Mon=0
    if weekday in rest_days:
        return {
            "date": now.isoformat(),
            "is_rest_day": True,
            "split_name": "Rest",
            "focus": "Regeneration",
            "exercises": [],
        }

    idx = (now - anchor).days % len(rotation)
    split_name = rotation[idx]
    split = protocol.get("splits", {}).get(split_name, {})

    return {
        "date": now.isoformat(),
        "is_rest_day": False,
        "split_name": split_name,
        "focus": split.get("focus", ""),
        "exercises": split.get("exercises", []),
        "notes": protocol.get("notes", []),
    }


def format_split_text(view: dict[str, Any]) -> str:
    if view.get("is_rest_day"):
        return "🏋️ Heute: Rest / aktive Regeneration"

    lines = [f"🏋️ Heute: {view.get('split_name', 'Training')} ({view.get('focus', '').strip()})"]
    for ex in view.get("exercises", [])[:6]:
        lines.append(f"  ☐ {ex}")
    return "\n".join(lines)
