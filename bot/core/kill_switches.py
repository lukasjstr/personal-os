"""G4: Kill switches for automations — emergency disable for scheduler jobs.

Kill switches are stored in a JSON file on disk. Setting a switch disables
the corresponding automation immediately without requiring a restart.

Usage:
    from bot.core.kill_switches import is_enabled, disable, enable, status

Switches:
    morning_brief       — daily morning brief messages
    evening_review      — daily evening review trigger
    weekly_reflection   — Sunday reflection trigger
    daily_suggestions   — daily GPT-4o suggestion generation
    autopilot_nudges    — autopilot notification sending
    achievement_checks  — automatic achievement unlock checks
"""
import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_SWITCH_FILE = Path("/opt/personal-os/config/kill_switches.json")

# Default: all automations enabled
_DEFAULTS: dict[str, bool] = {
    "morning_brief": True,
    "evening_review": True,
    "weekly_reflection": True,
    "daily_suggestions": True,
    "autopilot_nudges": True,
    "achievement_checks": True,
}


def _load() -> dict[str, bool]:
    if not _SWITCH_FILE.exists():
        return dict(_DEFAULTS)
    try:
        data = json.loads(_SWITCH_FILE.read_text())
        return {k: bool(data.get(k, v)) for k, v in _DEFAULTS.items()}
    except Exception as e:
        logger.warning("Failed to read kill switches: %s", e)
        return dict(_DEFAULTS)


def _save(switches: dict[str, bool]) -> None:
    try:
        _SWITCH_FILE.parent.mkdir(parents=True, exist_ok=True)
        _SWITCH_FILE.write_text(json.dumps(switches, indent=2))
    except Exception as e:
        logger.error("Failed to write kill switches: %s", e)


def is_enabled(switch: str) -> bool:
    """Return True if the automation switch is enabled (default: True)."""
    switches = _load()
    return switches.get(switch, True)


def disable(switch: str) -> bool:
    """Disable an automation. Returns True if the switch existed."""
    if switch not in _DEFAULTS:
        logger.warning("Unknown kill switch: %s", switch)
        return False
    switches = _load()
    switches[switch] = False
    _save(switches)
    logger.warning("Kill switch DISABLED: %s", switch)
    return True


def enable(switch: str) -> bool:
    """Re-enable a disabled automation. Returns True if the switch existed."""
    if switch not in _DEFAULTS:
        return False
    switches = _load()
    switches[switch] = True
    _save(switches)
    logger.info("Kill switch ENABLED: %s", switch)
    return True


def status() -> dict[str, Any]:
    """Return current state of all kill switches."""
    switches = _load()
    return {
        "switches": switches,
        "disabled_count": sum(1 for v in switches.values() if not v),
        "switch_file": str(_SWITCH_FILE),
        "file_exists": _SWITCH_FILE.exists(),
    }
