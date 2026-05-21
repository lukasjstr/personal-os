"""V3 P08 — Expansion Guard + /cut tests."""
import asyncio
import os
from datetime import datetime, timedelta

import pytest
from sqlalchemy import and_, delete, select

from bot.config import settings
from bot.core.objectives import (
    ExpansionGuardException,
    PRIORITY1_THRESHOLD,
    create_objective_with_guard,
    pause_objective_for_cut,
    suggest_objective_to_cut,
)
from bot.database.connection import engine, get_session
from bot.database.models import Objective, User


TEST_MARKER = "[v3-p08-test]"

requires_db = pytest.mark.skipif(
    not os.environ.get("PERSONAL_OS_DB_AVAILABLE"),
    reason="DB not available",
)


async def _get_user() -> User:
    async with get_session() as session:
        return (await session.execute(select(User).order_by(User.id).limit(1))).scalar_one()


async def _cleanup(user_id: int) -> None:
    async with get_session() as session:
        await session.execute(delete(Objective).where(and_(
            Objective.user_id == user_id,
            Objective.title.ilike(f"%{TEST_MARKER}%"),
        )))


async def _make_active_obj(user_id: int, title: str, priority_weight: int = 5) -> int:
    async with get_session() as session:
        obj = Objective(
            user_id=user_id,
            title=f"{TEST_MARKER} {title}",
            category="personal",
            status="active",
            priority_weight=priority_weight,
        )
        session.add(obj)
        await session.flush()
        return obj.id


# ─── Pure constants ───────────────────────────────────────────────────────────

def test_priority1_threshold_is_8() -> None:
    assert PRIORITY1_THRESHOLD == 8


def test_settings_carry_expansion_limits() -> None:
    assert settings.expansion_soft_limit_priority1 == 3
    assert settings.expansion_hard_limit_total == 5


# ─── Integration tests ────────────────────────────────────────────────────────

@requires_db
def test_hard_limit_blocks_sixth_objective() -> None:
    async def run() -> None:
        user = await _get_user()
        await _cleanup(user.id)
        # Start clean: deactivate ALL active objectives for this user first
        async with get_session() as session:
            actives = (await session.execute(
                select(Objective).where(and_(
                    Objective.user_id == user.id,
                    Objective.status == "active",
                ))
            )).scalars().all()
            saved_states = [(o.id, o.status) for o in actives]
            for o in actives:
                o.status = "paused"
            await session.flush()
        try:
            # Create 5 active test objectives = hard limit hit
            for i in range(5):
                await _make_active_obj(user.id, f"obj-{i}", priority_weight=5)
            # Trying the 6th must raise
            async with get_session() as session:
                with pytest.raises(ExpansionGuardException):
                    await create_objective_with_guard(
                        session, user.id,
                        title=f"{TEST_MARKER} sixth",
                        category="personal",
                        priority_weight=5,
                    )
        finally:
            await _cleanup(user.id)
            # Restore prior states
            async with get_session() as session:
                for (oid, st) in saved_states:
                    obj = await session.get(Objective, oid)
                    if obj is not None:
                        obj.status = st
                await session.flush()
            await engine.dispose()

    asyncio.run(run())


@requires_db
def test_soft_limit_emits_warning_but_creates() -> None:
    async def run() -> None:
        user = await _get_user()
        await _cleanup(user.id)
        async with get_session() as session:
            actives = (await session.execute(
                select(Objective).where(and_(
                    Objective.user_id == user.id,
                    Objective.status == "active",
                ))
            )).scalars().all()
            saved_states = [(o.id, o.status) for o in actives]
            for o in actives:
                o.status = "paused"
            await session.flush()
        try:
            # Create 3 P1 (priority_weight=8) objectives
            for i in range(3):
                await _make_active_obj(user.id, f"p1-{i}", priority_weight=8)
            # 4th P1 attempt → soft warning, but row created
            async with get_session() as session:
                result = await create_objective_with_guard(
                    session, user.id,
                    title=f"{TEST_MARKER} fourth-p1",
                    category="personal",
                    priority_weight=8,
                )
            assert result["warning"] is not None
            assert "SOFT LIMIT" in result["warning"]
            assert result["objective"] is not None
            assert result["stats"]["priority1_count"] == 4
        finally:
            await _cleanup(user.id)
            async with get_session() as session:
                for (oid, st) in saved_states:
                    obj = await session.get(Objective, oid)
                    if obj is not None:
                        obj.status = st
                await session.flush()
            await engine.dispose()

    asyncio.run(run())


@requires_db
def test_suggest_objective_to_cut_returns_weakest() -> None:
    async def run() -> None:
        user = await _get_user()
        try:
            async with get_session() as session:
                cut = await suggest_objective_to_cut(session, user.id)
            # Either we have active objectives → returns dict; or none → None.
            if cut is not None:
                assert "id" in cut and "title" in cut
                assert "days_stale" in cut and "completion" in cut
                assert "score" in cut
        finally:
            await engine.dispose()

    asyncio.run(run())


@requires_db
def test_pause_objective_for_cut_sets_paused_fields() -> None:
    async def run() -> None:
        user = await _get_user()
        await _cleanup(user.id)
        try:
            obj_id = await _make_active_obj(user.id, "to-be-cut", priority_weight=5)
            async with get_session() as session:
                paused = await pause_objective_for_cut(session, user.id, obj_id)
            assert paused is not None
            assert paused.status == "paused"
            assert paused.paused_at is not None
            assert paused.paused_reason == "expansion_cut"

            async with get_session() as session:
                fresh = await session.get(Objective, obj_id)
                assert fresh.status == "paused"
                assert fresh.paused_reason == "expansion_cut"
        finally:
            await _cleanup(user.id)
            await engine.dispose()

    asyncio.run(run())


@requires_db
def test_pause_objective_for_cut_returns_none_for_unknown() -> None:
    async def run() -> None:
        user = await _get_user()
        try:
            async with get_session() as session:
                result = await pause_objective_for_cut(session, user.id, 999_999_999)
            assert result is None
        finally:
            await engine.dispose()

    asyncio.run(run())
