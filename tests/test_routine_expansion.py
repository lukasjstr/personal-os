"""V3 P04 — Routine → CalendarEvent expansion parser tests.

Pure unit tests for `parse_frequency_human` (no DB).
"""
import pytest

from bot.core.calendar import parse_frequency_human


def test_parse_daily_de() -> None:
    assert parse_frequency_human("Täglich") == {0, 1, 2, 3, 4, 5, 6}


def test_parse_daily_en() -> None:
    assert parse_frequency_human("Daily") == {0, 1, 2, 3, 4, 5, 6}


def test_parse_weekday_slashes() -> None:
    assert parse_frequency_human("Mo/Mi/Fr") == {0, 2, 4}


def test_parse_weekday_commas() -> None:
    assert parse_frequency_human("Di, Do") == {1, 3}


def test_parse_jeden_dienstag() -> None:
    assert parse_frequency_human("Jeden Dienstag") == {1}


def test_parse_weekly_defaults_monday() -> None:
    assert parse_frequency_human("wöchentlich") == {0}
    assert parse_frequency_human("weekly") == {0}


def test_parse_3x_pro_woche() -> None:
    assert parse_frequency_human("3x pro Woche") == {0, 2, 4}


def test_parse_2x_pro_woche() -> None:
    assert parse_frequency_human("2x pro Woche") == {1, 3}


def test_parse_5x_pro_woche() -> None:
    assert parse_frequency_human("5x pro Woche") == {0, 1, 2, 3, 4}


def test_parse_empty_defaults_monday() -> None:
    assert parse_frequency_human("") == {0}


def test_parse_unknown_defaults_monday() -> None:
    # Garbage input → safe default (don't crash, pick Monday)
    assert parse_frequency_human("xyzzy") == {0}
