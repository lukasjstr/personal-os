"""Unit tests for V3 P03 — Coach-Modus.

These tests cover deterministic pieces only:
- the softener detector (regex-based)
- the system prompt structure (must contain all 3 new blocks)
- the new `list_active_objectives` tool registration

GPT-4o output is non-deterministic; live AI tests belong in a manual
verification step ('5 Test-Messages, mindestens 4 davon ohne Verniedlichungen').
"""
from bot.ai.client import detect_softeners, sanitize_reply
from bot.ai.prompts import SYSTEM_PROMPT
from bot.ai.tools import TOOLS


# ─── Softener detector ────────────────────────────────────────────────────────

def test_detect_softeners_finds_bitte() -> None:
    assert detect_softeners("Bitte mach Cardio heute.") == ["Bitte"]


def test_detect_softeners_finds_gerne() -> None:
    assert "gerne" in [s.lower() for s in detect_softeners("Mach ich gerne für dich.")]


def test_detect_softeners_finds_super_with_punctuation() -> None:
    hits = [s.lower() for s in detect_softeners("Super! Du hast 5 Tasks gemacht.")]
    assert any(h.startswith("super") for h in hits)


def test_detect_softeners_ignores_supercomputer() -> None:
    # 'super' without trailing ! or . must not match the cheer pattern
    assert detect_softeners("Das ist ein Supercomputer.") == []


def test_detect_softeners_finds_multiple() -> None:
    hits = [s.lower() for s in detect_softeners("Natürlich! Klasse! Bitte mach das.")]
    assert any(h.startswith("nat") for h in hits)
    assert any(h.startswith("klasse") for h in hits)
    assert any(h.startswith("bitte") for h in hits)


def test_detect_softeners_clean_reply() -> None:
    coach_reply = "Cardio fehlt diese Woche. 1/3. Heute 18:00 Treadmill — Slot ist frei."
    assert detect_softeners(coach_reply) == []


def test_sanitize_reply_returns_input_unchanged() -> None:
    msg = "Bitte. Super! Wunderbar!"
    assert sanitize_reply(msg, user_id=1) == msg


# ─── System prompt structure ──────────────────────────────────────────────────

def test_system_prompt_has_coach_mode_block() -> None:
    assert "COACH-MODUS" in SYSTEM_PROMPT
    assert "KEIN ASSISTANT-MODUS" in SYSTEM_PROMPT
    assert 'KEIN "Bitte"' in SYSTEM_PROMPT


def test_system_prompt_has_bedrock_aktiv_block() -> None:
    assert "BEDROCK-AKTIV" in SYSTEM_PROMPT
    assert "9 Lebensbereiche" in SYSTEM_PROMPT
    assert "Leitspruch" in SYSTEM_PROMPT


def test_system_prompt_has_expansion_protection_block() -> None:
    assert "EXPANSIONSSCHUTZ" in SYSTEM_PROMPT
    assert "list_active_objectives" in SYSTEM_PROMPT
    assert "4 aktive Objectives" in SYSTEM_PROMPT or "≥ 4" in SYSTEM_PROMPT


def test_system_prompt_blocks_appear_before_parallel_extraktion() -> None:
    """The 3 new blocks must be evaluated BEFORE PARALLEL-EXTRAKTION."""
    pos_coach = SYSTEM_PROMPT.index("COACH-MODUS")
    pos_bedrock = SYSTEM_PROMPT.index("BEDROCK-AKTIV")
    pos_expansion = SYSTEM_PROMPT.index("EXPANSIONSSCHUTZ")
    pos_kernprinzip = SYSTEM_PROMPT.index("KERNPRINZIP: PARALLEL-EXTRAKTION")
    assert pos_coach < pos_kernprinzip
    assert pos_bedrock < pos_kernprinzip
    assert pos_expansion < pos_kernprinzip


# ─── Tool registration ────────────────────────────────────────────────────────

def test_list_active_objectives_tool_registered() -> None:
    names = [t["function"]["name"] for t in TOOLS]
    assert "list_active_objectives" in names


def test_list_active_objectives_tool_has_no_required_params() -> None:
    tool = next(t for t in TOOLS if t["function"]["name"] == "list_active_objectives")
    params = tool["function"]["parameters"]
    assert params["type"] == "object"
    assert params.get("required", []) == []
