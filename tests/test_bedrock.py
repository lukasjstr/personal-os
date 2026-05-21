"""Unit tests for the bedrock identity layer (V3 P02)."""
from bot.core.life_profile import format_bedrock


SAMPLE = {
    "identity": {
        "name": "Lukas",
        "current_location": "Bangkok",
        "home_country": "Deutschland",
        "company": "Blaue Adler",
        "co_founders": ["Nils", "Philipp"],
        "launch_target": "Juni/Juli 2026",
    },
    "life_areas": [
        {"name": "Physical", "vision": "~85kg, Leonidas/Spartan look"},
        {"name": "Money/Business", "vision": "10k/mo → 36M"},
    ],
    "skill_levers": [
        {"name": "Selbstführung & Organisation", "description": "Bottleneck", "priority": 1},
        {"name": "Vertrieb & Verhandlung", "description": "Türen", "priority": 2},
    ],
    "self_leadership_competencies": ["Klarheit", "Emotionsregulation"],
    "leitspruch": "Ich expandiere wenn kein Cut kommt.",
    "weaknesses": ["Zu viel parallel"],
    "bottleneck": "Layer 2",
    "communication_style": "direkt, du-Form, max 4 Sätze",
}


def test_format_bedrock_includes_identity() -> None:
    out = format_bedrock(SAMPLE)
    assert "Lukas" in out
    assert "Bangkok" in out
    assert "Blaue Adler" in out
    assert "Nils" in out and "Philipp" in out


def test_format_bedrock_includes_leitspruch() -> None:
    out = format_bedrock(SAMPLE)
    assert "Ich expandiere wenn kein Cut kommt." in out
    assert "LEITSPRUCH" in out


def test_format_bedrock_includes_bottleneck_and_weaknesses() -> None:
    out = format_bedrock(SAMPLE)
    assert "BOTTLENECK" in out
    assert "Layer 2" in out
    assert "Zu viel parallel" in out


def test_format_bedrock_lists_life_areas_in_order() -> None:
    out = format_bedrock(SAMPLE)
    assert "1. Physical" in out
    assert "2. Money/Business" in out
    assert "Leonidas" in out


def test_format_bedrock_sorts_levers_by_priority() -> None:
    out = format_bedrock(SAMPLE)
    p1_idx = out.index("P1 Selbstführung & Organisation")
    p2_idx = out.index("P2 Vertrieb & Verhandlung")
    assert p1_idx < p2_idx  # priority 1 must appear before priority 2


def test_format_bedrock_empty_returns_empty_string() -> None:
    assert format_bedrock({}) == ""


def test_format_bedrock_partial_does_not_crash() -> None:
    # Only identity — no leitspruch, no life_areas etc.
    out = format_bedrock({"identity": {"name": "Lukas", "current_location": "Bangkok"}})
    assert "Lukas" in out
    assert "Bangkok" in out
    # Sections that have no data must be skipped
    assert "LEITSPRUCH" not in out
    assert "9 LEBENSBEREICHE" not in out


def test_format_bedrock_includes_communication_style() -> None:
    out = format_bedrock(SAMPLE)
    assert "KOMMUNIKATIONS-STIL" in out
    assert "direkt, du-Form, max 4 Sätze" in out
