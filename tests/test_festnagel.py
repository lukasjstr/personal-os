"""V3 P05 — Festnagel generator + morning brief structure tests.

The integration tests require the production DB (PERSONAL_OS_DB_AVAILABLE=1).
The fallback test is pure (no DB).
"""
import asyncio
import os
from datetime import date, datetime, timedelta

import pytest

from bot.core.festnagel import (
    _fallback,
    generate_brief_status,
    generate_dropout_outlook,
    generate_festnagel,
    generate_three_musts,
)


requires_db = pytest.mark.skipif(
    not os.environ.get("PERSONAL_OS_DB_AVAILABLE"),
    reason="DB not available (set PERSONAL_OS_DB_AVAILABLE=1 to run)",
)


# ─── Pure tests (no DB) ───────────────────────────────────────────────────────

def test_fallback_weekend_is_solitude() -> None:
    saturday = date(2026, 5, 23)  # Saturday
    sunday = date(2026, 5, 24)  # Sunday
    assert "Solitude" in _fallback(saturday) or "Wochenende" in _fallback(saturday)
    assert _fallback(saturday) == _fallback(sunday)


def test_fallback_midweek_demands_recovery() -> None:
    wednesday = date(2026, 5, 20)  # Wed
    thursday = date(2026, 5, 21)  # Thu
    out = _fallback(wednesday)
    assert "Mid" in out or "Mo+Di" in out
    assert _fallback(wednesday) == _fallback(thursday)


def test_fallback_other_weekdays_offers_morning_slot() -> None:
    monday = date(2026, 5, 18)
    assert "11:00" in _fallback(monday)


# ─── Integration tests (real DB) ──────────────────────────────────────────────

@requires_db
def test_festnagel_never_empty() -> None:
    """For any existing user, generate_festnagel must return a non-empty line."""
    from bot.database.connection import engine, get_session
    from bot.database.models import User
    from sqlalchemy import select

    async def run() -> None:
        try:
            async with get_session() as session:
                user = (await session.execute(
                    select(User).order_by(User.id).limit(1)
                )).scalar_one_or_none()
                assert user is not None, "no users in DB"
                line = await generate_festnagel(session, user.id)
                assert isinstance(line, str)
                assert len(line.strip()) > 10
        finally:
            await engine.dispose()

    asyncio.run(run())


@requires_db
def test_brief_status_returns_counts() -> None:
    from bot.database.connection import engine, get_session
    from bot.database.models import User
    from sqlalchemy import select

    async def run() -> None:
        try:
            async with get_session() as session:
                user = (await session.execute(select(User).order_by(User.id).limit(1))).scalar_one()
                status = await generate_brief_status(session, user.id, date.today())
                assert "active_objectives" in status
                assert "krs_at_risk" in status
                assert isinstance(status["active_objectives"], int)
                assert isinstance(status["krs_at_risk"], int)
        finally:
            await engine.dispose()

    asyncio.run(run())


@requires_db
def test_three_musts_returns_list_of_dicts() -> None:
    from bot.database.connection import engine, get_session
    from bot.database.models import User
    from sqlalchemy import select

    async def run() -> None:
        try:
            async with get_session() as session:
                user = (await session.execute(select(User).order_by(User.id).limit(1))).scalar_one()
                musts = await generate_three_musts(session, user.id, date.today())
                assert isinstance(musts, list)
                assert len(musts) <= 3
                for m in musts:
                    assert m["kind"] in ("task", "routine", "kr")
                    assert isinstance(m["title"], str)
        finally:
            await engine.dispose()

    asyncio.run(run())


@requires_db
def test_morgen_brief_contains_festnagel_section() -> None:
    """The full brief must contain the FESTNAGEL section + a non-trivial line."""
    from bot.database.connection import engine, get_session
    from bot.database.models import User
    from bot.jobs.morning_brief import _generate_brief_for_user
    from sqlalchemy import select
    from zoneinfo import ZoneInfo

    async def run() -> None:
        try:
            async with get_session() as session:
                user = (await session.execute(select(User).order_by(User.id).limit(1))).scalar_one()
                today = date.today()
                now_berlin = datetime.now(tz=ZoneInfo("Europe/Berlin"))
                brief_text, _priorities = await _generate_brief_for_user(
                    session, user, today, now_berlin
                )
            assert "━━ FESTNAGEL ━━" in brief_text
            # Extract the line right after the FESTNAGEL header
            parts = brief_text.split("━━ FESTNAGEL ━━", 1)
            assert len(parts) == 2
            festnagel_line = parts[1].splitlines()[1] if len(parts[1].splitlines()) > 1 else parts[1].splitlines()[0]
            assert len(festnagel_line.strip()) > 10, f"Festnagel line too short: {festnagel_line!r}"
            # Must have STATUS section too
            assert "━━ STATUS ━━" in brief_text
        finally:
            await engine.dispose()

    asyncio.run(run())
