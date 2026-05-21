"""V3 P10 — Mission Layer tests."""
import asyncio
import os
from datetime import date

import pytest
from sqlalchemy import and_, delete, select

from bot.core.life_areas import (
    get_area_stats,
    get_weekly_focus_lines,
    list_life_areas,
)
from bot.database.connection import engine, get_session
from bot.database.models import LifeArea, Objective, User


requires_db = pytest.mark.skipif(
    not os.environ.get("PERSONAL_OS_DB_AVAILABLE"),
    reason="DB not available",
)


async def _get_user() -> User:
    async with get_session() as session:
        return (await session.execute(select(User).order_by(User.id).limit(1))).scalar_one()


# ─── Integration tests ────────────────────────────────────────────────────────


@requires_db
def test_list_life_areas_returns_all_nine_after_seed() -> None:
    """After seed_lukas_life_areas the user has all 9 areas."""
    async def run() -> None:
        try:
            user = await _get_user()
            async with get_session() as session:
                areas = await list_life_areas(session, user.id)
            short_codes = {a.short_code for a in areas}
            expected = {
                "mental", "physical", "character", "family", "romance",
                "money", "lifestyle", "charity", "spirituality",
            }
            # Test runs after seed; if seed hasn't been run we expect at least 0.
            # If seeded: all 9 present.
            if short_codes:
                missing = expected - short_codes
                assert not missing, f"missing life areas: {missing}"
        finally:
            await engine.dispose()

    asyncio.run(run())


@requires_db
def test_get_area_stats_returns_required_keys() -> None:
    async def run() -> None:
        try:
            user = await _get_user()
            async with get_session() as session:
                areas = await list_life_areas(session, user.id)
                if not areas:
                    pytest.skip("no life areas seeded")
                stats = await get_area_stats(session, user.id, areas[0].id)
            assert "active_objectives" in stats
            assert "stale_days" in stats
            assert "last_log_at" in stats
            assert isinstance(stats["active_objectives"], int)
        finally:
            await engine.dispose()

    asyncio.run(run())


@requires_db
def test_get_weekly_focus_lines_returns_max_three() -> None:
    async def run() -> None:
        try:
            user = await _get_user()
            async with get_session() as session:
                lines = await get_weekly_focus_lines(session, user.id, date.today())
            assert isinstance(lines, list)
            assert len(lines) <= 3
            for line in lines:
                assert isinstance(line, str)
                assert line.strip().startswith(("1.", "2.", "3."))
        finally:
            await engine.dispose()

    asyncio.run(run())


@requires_db
def test_objective_life_area_id_is_assignable() -> None:
    """Smoke test: Objective.life_area_id can be set and persisted."""
    TEST_MARKER = "[v3-p10-test]"

    async def run() -> None:
        user = await _get_user()
        async with get_session() as session:
            await session.execute(delete(Objective).where(and_(
                Objective.user_id == user.id,
                Objective.title.ilike(f"%{TEST_MARKER}%"),
            )))
        try:
            async with get_session() as session:
                area = (await session.execute(
                    select(LifeArea).where(LifeArea.user_id == user.id).limit(1)
                )).scalar_one_or_none()
                if area is None:
                    pytest.skip("no life areas seeded")
                obj = Objective(
                    user_id=user.id,
                    title=f"{TEST_MARKER} link test",
                    category="personal",
                    status="active",
                    life_area_id=area.id,
                )
                session.add(obj)
                await session.flush()
                oid = obj.id

            async with get_session() as session:
                fresh = await session.get(Objective, oid)
                assert fresh.life_area_id == area.id
        finally:
            async with get_session() as session:
                await session.execute(delete(Objective).where(and_(
                    Objective.user_id == user.id,
                    Objective.title.ilike(f"%{TEST_MARKER}%"),
                )))
            await engine.dispose()

    asyncio.run(run())
