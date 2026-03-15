from datetime import date

from bot.core.supplement_protocol import cycle_state, generate_daily_checklist, load_protocol


def test_cycle_state_on_off_window() -> None:
    anchor = date(2026, 3, 16)
    cycle = {"days_on": 5, "days_off": 2}

    d1 = cycle_state(cycle, anchor, anchor)
    assert d1.active is True
    assert d1.block_type == "on"
    assert d1.day_in_block == 1

    d6 = cycle_state(cycle, date(2026, 3, 21), anchor)
    assert d6.active is False
    assert d6.block_type == "off"
    assert d6.day_in_block == 1

    d8 = cycle_state(cycle, date(2026, 3, 23), anchor)
    assert d8.active is True
    assert d8.day_in_block == 1


def test_checklist_hides_cycled_items_when_off() -> None:
    protocol = load_protocol()
    # 2026-03-21 is day 6 since anchor -> off-day for 5/2 cycles (rhodiola/shilajit)
    checklist = generate_daily_checklist(protocol, date(2026, 3, 21))

    morning_names = {i["name"] for i in checklist["slot_checklist"]["morning"]}
    midday_names = {i["name"] for i in checklist["slot_checklist"]["midday"]}

    assert "Rhodiola rosea" not in morning_names
    assert "Shilajit" not in midday_names
    assert checklist["medical_disclaimer"].startswith("Hinweis: Kein medizinischer Rat")
