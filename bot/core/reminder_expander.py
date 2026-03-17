"""Reminder repeat-rule parser and expander.

repeat_rule format:
    "daily:HH:MM[,HH:MM...]"        → fires every day at given times
    "weekly:HH:MM:WEEKDAY"          → fires weekly, WEEKDAY=0(Mon)–6(Sun)
    "once"                          → fires once (no repeat)
"""
from __future__ import annotations


def parse_repeat_rule(rule: str) -> tuple[str, list[str], int | None]:
    """Parse a repeat_rule string.

    Returns:
        (frequency, times, weekday)

        frequency: "daily" | "weekly" | "once"
        times: list of "HH:MM" strings
        weekday: 0-6 (Monday=0) for weekly rules, else None
    """
    if not rule or rule == "once":
        return "once", [], None

    parts = rule.split(":", 1)
    frequency = parts[0].lower()

    if frequency == "daily":
        # "daily:09:00,13:00,17:00"
        rest = parts[1] if len(parts) > 1 else "09:00"
        times = [t.strip() for t in rest.split(",") if t.strip()]
        return "daily", times, None

    if frequency == "weekly":
        # "weekly:09:00:1"  → every Tuesday at 09:00
        rest = parts[1] if len(parts) > 1 else "09:00:0"
        rest_parts = rest.split(":")
        time_str = f"{rest_parts[0]}:{rest_parts[1]}" if len(rest_parts) >= 2 else "09:00"
        weekday = int(rest_parts[2]) if len(rest_parts) >= 3 else 0
        return "weekly", [time_str], weekday

    # Fallback: treat as daily with the full remainder as a single time
    rest = parts[1] if len(parts) > 1 else "09:00"
    times = [rest.split(",")[0].strip()]
    return "daily", times, None
