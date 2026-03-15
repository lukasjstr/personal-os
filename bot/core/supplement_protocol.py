"""Supplement protocol config + daily checklist generation.

Additive helper used by planner/brief flows.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
import json
from pathlib import Path
from typing import Any


DEFAULT_PROTOCOL_PATH = (
    Path(__file__).resolve().parents[2]
    / "docs"
    / "protocols"
    / "lukas_keto_supplements.json"
)

MEDICAL_DISCLAIMER = (
    "Hinweis: Kein medizinischer Rat. Supplemente und Dosierungen immer mit "
    "Arzt/Blutwerten/GI-Verträglichkeit abgleichen."
)


@dataclass(frozen=True)
class CycleState:
    active: bool
    day_in_block: int
    block_type: str


def load_protocol(path: Path | str | None = None) -> dict[str, Any]:
    """Load protocol JSON from disk."""
    protocol_path = Path(path) if path else DEFAULT_PROTOCOL_PATH
    with protocol_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _parse_anchor_date(protocol: dict[str, Any]) -> date:
    anchor_str = (
        protocol.get("cycle_anchor_date")
        or protocol.get("meta", {}).get("cycle_anchor_date")
        or "2026-01-01"
    )
    return datetime.strptime(anchor_str, "%Y-%m-%d").date()


def cycle_state(cycle: dict[str, Any], target_date: date, anchor_date: date) -> CycleState:
    """Return whether cyclical supplement is active on the given day.

    Cycle format:
      - days_on, days_off
    """
    days_on = int(cycle.get("days_on", 0))
    days_off = int(cycle.get("days_off", 0))
    total = days_on + days_off
    if total <= 0:
        return CycleState(active=True, day_in_block=1, block_type="always_on")

    offset = (target_date - anchor_date).days
    idx = offset % total
    if idx < days_on:
        return CycleState(active=True, day_in_block=idx + 1, block_type="on")
    return CycleState(active=False, day_in_block=(idx - days_on) + 1, block_type="off")


def generate_daily_checklist(
    protocol: dict[str, Any],
    target_date: date | None = None,
) -> dict[str, Any]:
    """Generate today's supplement checklist with cycle gating."""
    current_date = target_date or date.today()
    anchor = _parse_anchor_date(protocol)

    slots = protocol.get("stacks", {})
    cyclical = protocol.get("cycles", {})

    cycle_states: dict[str, dict[str, Any]] = {}
    for name, cycle in cyclical.items():
        st = cycle_state(cycle, current_date, anchor)
        cycle_states[name] = {
            "active": st.active,
            "day_in_block": st.day_in_block,
            "block_type": st.block_type,
        }

    def _slot_items(slot_name: str) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for item in slots.get(slot_name, []):
            cycle_key = item.get("cycle_key")
            if cycle_key:
                st = cycle_states.get(cycle_key)
                if st and not st["active"]:
                    continue
            out.append(item)
        return out

    return {
        "date": current_date.isoformat(),
        "medical_disclaimer": MEDICAL_DISCLAIMER,
        "macro_targets": protocol.get("macro_targets", {}),
        "micro_targets": protocol.get("micro_targets", {}),
        "hydration": protocol.get("hydration", {}),
        "slot_checklist": {
            "morning": _slot_items("morning"),
            "midday": _slot_items("midday"),
            "evening": _slot_items("evening"),
            "daily": _slot_items("daily"),
            "optional": _slot_items("optional"),
        },
        "cycle_states": cycle_states,
        "notes": protocol.get("notes", []),
        "synergies": protocol.get("synergies", []),
    }
