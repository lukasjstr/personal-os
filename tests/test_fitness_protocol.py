from datetime import date

from bot.core.fitness_protocol import format_split_text, get_today_split, load_fitness_protocol


def test_rotation_returns_expected_split_from_anchor() -> None:
    protocol = load_fitness_protocol()
    # Anchor day -> first in rotation
    day1 = get_today_split(protocol, date(2026, 3, 16))
    day2 = get_today_split(protocol, date(2026, 3, 17))
    day3 = get_today_split(protocol, date(2026, 3, 18))
    day4 = get_today_split(protocol, date(2026, 3, 19))

    assert day1["split_name"] == "Beine"
    assert day2["split_name"] == "Pull"
    assert day3["split_name"] == "Push"
    assert day4["split_name"] == "Beine"


def test_format_split_text_contains_exercises() -> None:
    protocol = load_fitness_protocol()
    view = get_today_split(protocol, date(2026, 3, 16))
    text = format_split_text(view)

    assert "Heute: Beine" in text
    assert "Beinpresse" in text
