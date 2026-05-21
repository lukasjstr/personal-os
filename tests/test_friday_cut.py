"""V3 P09 — Friday-Cut tests."""
import asyncio
import os
from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import and_, delete, select

from bot.core.friday_cut import (
    build_friday_cut_prompt,
    count_cuts_this_week,
    cut_free_text,
    cut_task,
)
from bot.database.connection import engine, get_session
from bot.database.models import BrainDump, Task, User


TEST_MARKER = "[v3-p09-test]"

requires_db = pytest.mark.skipif(
    not os.environ.get("PERSONAL_OS_DB_AVAILABLE"),
    reason="DB not available",
)


async def _get_user() -> User:
    async with get_session() as session:
        return (await session.execute(select(User).order_by(User.id).limit(1))).scalar_one()


async def _cleanup(user_id: int) -> None:
    async with get_session() as session:
        await session.execute(delete(BrainDump).where(and_(
            BrainDump.user_id == user_id,
            BrainDump.raw_input.ilike(f"%{TEST_MARKER}%"),
        )))
        await session.execute(delete(Task).where(and_(
            Task.user_id == user_id,
            Task.title.ilike(f"%{TEST_MARKER}%"),
        )))


async def _make_task(user_id: int, title: str) -> int:
    async with get_session() as session:
        t = Task(
            user_id=user_id,
            title=f"{TEST_MARKER} {title}",
            status="todo",
            priority=3,
        )
        session.add(t)
        await session.flush()
        return t.id


# ─── Integration tests ────────────────────────────────────────────────────────

@requires_db
def test_cut_task_marks_cancelled_and_archives() -> None:
    async def run() -> None:
        user = await _get_user()
        await _cleanup(user.id)
        try:
            tid = await _make_task(user.id, "throwaway")
            async with get_session() as session:
                task = await cut_task(session, user.id, tid)
            assert task is not None
            assert task.status == "cancelled"
            assert task.cancelled_reason == "friday_cut"
            assert task.cancelled_at is not None

            async with get_session() as session:
                fresh = await session.get(Task, tid)
                assert fresh.status == "cancelled"
                # Brain-dump archive entry exists
                dumps = (await session.execute(
                    select(BrainDump).where(and_(
                        BrainDump.user_id == user.id,
                        BrainDump.raw_input.like("%friday_cut_archive%"),
                        BrainDump.raw_input.ilike(f"%{TEST_MARKER}%"),
                    ))
                )).scalars().all()
                assert len(dumps) >= 1
        finally:
            await _cleanup(user.id)
            await engine.dispose()

    asyncio.run(run())


@requires_db
def test_cut_task_returns_none_for_unknown() -> None:
    async def run() -> None:
        try:
            user = await _get_user()
            async with get_session() as session:
                result = await cut_task(session, user.id, 999_999_999)
            assert result is None
        finally:
            await engine.dispose()

    asyncio.run(run())


@requires_db
def test_cut_free_text_creates_braindump_with_tag() -> None:
    async def run() -> None:
        user = await _get_user()
        await _cleanup(user.id)
        try:
            async with get_session() as session:
                dump = await cut_free_text(session, user.id, f"{TEST_MARKER} freetext cut")
            assert dump is not None
            assert "friday_cut_archive" in dump.raw_input
            assert TEST_MARKER in dump.raw_input
        finally:
            await _cleanup(user.id)
            await engine.dispose()

    asyncio.run(run())


@requires_db
def test_count_cuts_this_week_counts_only_marked_rows() -> None:
    async def run() -> None:
        user = await _get_user()
        await _cleanup(user.id)
        try:
            t1 = await _make_task(user.id, "cut-1")
            t2 = await _make_task(user.id, "cut-2")
            async with get_session() as session:
                await cut_task(session, user.id, t1)
                await cut_task(session, user.id, t2)

            async with get_session() as session:
                n = await count_cuts_this_week(session, user.id)
            assert n >= 2, f"expected ≥2 cuts this week, got {n}"
        finally:
            await _cleanup(user.id)
            await engine.dispose()

    asyncio.run(run())


@requires_db
def test_build_friday_cut_prompt_contains_header_and_instruction() -> None:
    async def run() -> None:
        try:
            user = await _get_user()
            async with get_session() as session:
                msg = await build_friday_cut_prompt(session, user.id, date.today())
            assert "━━ FREITAG-CUT ━━" in msg
            assert "Was streichst du" in msg
            assert "Brain Dump" in msg or "/cut" in msg
        finally:
            await engine.dispose()

    asyncio.run(run())
