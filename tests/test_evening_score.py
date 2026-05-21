"""V3 P06 — Evening score + harter Punkt tests."""
import asyncio
import os
from datetime import date, datetime, timedelta

import pytest

from bot.core.evening_score import calculate_daily_score, generate_harter_punkt


requires_db = pytest.mark.skipif(
    not os.environ.get("PERSONAL_OS_DB_AVAILABLE"),
    reason="DB not available (set PERSONAL_OS_DB_AVAILABLE=1 to run)",
)


# ─── Integration tests (real DB) ──────────────────────────────────────────────

@requires_db
def test_calculate_daily_score_handles_user_without_brief() -> None:
    """Without a morning brief today, score should be small but valid."""
    from bot.database.connection import engine, get_session
    from bot.database.models import User
    from sqlalchemy import select

    async def run() -> None:
        try:
            async with get_session() as session:
                user = (await session.execute(select(User).order_by(User.id).limit(1))).scalar_one()
                # Use a far-future date so there's definitely no brief
                far_date = date.today() + timedelta(days=365)
                data = await calculate_daily_score(session, user.id, far_date)
                assert 0 <= data["score"] <= 10
                assert "harter_punkt" in data
                assert len(data["harter_punkt"]) > 5
                assert data["missed_must"] == []
        finally:
            await engine.dispose()

    asyncio.run(run())


@requires_db
def test_calculate_daily_score_returns_required_keys() -> None:
    from bot.database.connection import engine, get_session
    from bot.database.models import User
    from sqlalchemy import select

    async def run() -> None:
        try:
            async with get_session() as session:
                user = (await session.execute(select(User).order_by(User.id).limit(1))).scalar_one()
                data = await calculate_daily_score(session, user.id, date.today())
                # Required keys
                for key in ("score", "delivered", "missed_must", "best_thing",
                            "harter_punkt", "tomorrow_top"):
                    assert key in data, f"missing key: {key}"
                assert isinstance(data["score"], int)
                assert 0 <= data["score"] <= 10
                assert isinstance(data["delivered"], dict)
                assert "tasks" in data["delivered"] and "routines" in data["delivered"]
                assert isinstance(data["harter_punkt"], str)
                assert len(data["harter_punkt"]) > 10
        finally:
            await engine.dispose()

    asyncio.run(run())


@requires_db
def test_generate_harter_punkt_handles_missed_tasks() -> None:
    from bot.database.connection import engine, get_session
    from bot.database.models import User
    from sqlalchemy import select

    async def run() -> None:
        try:
            async with get_session() as session:
                user = (await session.execute(select(User).order_by(User.id).limit(1))).scalar_one()
                missed = ["Task A", "Task B"]
                line = await generate_harter_punkt(session, user.id, date.today(), missed)
                assert isinstance(line, str)
                assert len(line) > 10
                # Should reference either repeated misses, versprechensdisziplin,
                # the count of missed tasks today, or the "clean day" path.
                # All branches end with a confrontational line.
        finally:
            await engine.dispose()

    asyncio.run(run())


@requires_db
def test_generate_harter_punkt_clean_day_message() -> None:
    """Without misses and assuming no rolling drift, hp must still return a line."""
    from bot.database.connection import engine, get_session
    from bot.database.models import User
    from sqlalchemy import select

    async def run() -> None:
        try:
            async with get_session() as session:
                user = (await session.execute(select(User).order_by(User.id).limit(1))).scalar_one()
                line = await generate_harter_punkt(session, user.id, date.today(), [])
                # Could hit any branch depending on real data, just verify non-empty
                assert isinstance(line, str)
                assert len(line) > 5
        finally:
            await engine.dispose()

    asyncio.run(run())


@requires_db
def test_evening_review_contains_required_sections() -> None:
    """End-to-end: the assembled review text must contain all required headers."""
    from bot.database.connection import engine, get_session
    from bot.database.models import User
    from bot.jobs.evening_review import _generate_review_for_user, _get_or_create_daily_brief
    from sqlalchemy import select

    async def run() -> None:
        try:
            async with get_session() as session:
                user = (await session.execute(select(User).order_by(User.id).limit(1))).scalar_one()
                today = date.today()
                brief = await _get_or_create_daily_brief(session, user.id, today)
                text = await _generate_review_for_user(session, user, today, brief)
            # Required sections
            for header in ("━━ TAGES-SCORE ━━", "━━ GELIEFERT ━━", "━━ HARTER PUNKT ━━"):
                assert header in text, f"missing header: {header}"
            # Reply prompt
            assert "Mood 1-10" in text
            # Score line format
            score_line = text.split("━━ TAGES-SCORE ━━")[1].splitlines()[1]
            # Pattern: "N/10"
            assert "/10" in score_line, f"score line malformed: {score_line!r}"
        finally:
            await engine.dispose()

    asyncio.run(run())
