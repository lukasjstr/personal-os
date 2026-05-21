"""V3 P04 — Integration tests for proposal_execute → calendar event creation.

These tests hit a real Postgres DB (the same the bot uses). They are isolated
via a `[v3-p04-test]` marker in titles/descriptions and clean up after
themselves so re-runs are safe.

Skipped if PERSONAL_OS_DB_AVAILABLE is not set (e.g. local laptop without DB).
Run on the server:

    PYTHONPATH=. PERSONAL_OS_DB_AVAILABLE=1 python3 -m pytest \\
        tests/test_proposal_execute_calendar.py -v
"""
import asyncio
import os
from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import and_, delete, select

from bot.core.proposal_execute import execute_accepted_proposal
from bot.database.connection import engine, get_session
from bot.database.models import (
    AutopilotNotification,
    CalendarEvent,
    KeyResult,
    Objective,
    OKRProposalDraft,
    Routine,
    ScheduledReminder,
    Task,
    User,
)

TEST_MARKER = "[v3-p04-test]"

requires_db = pytest.mark.skipif(
    not os.environ.get("PERSONAL_OS_DB_AVAILABLE"),
    reason="DB not available (set PERSONAL_OS_DB_AVAILABLE=1 to run)",
)


async def _get_test_user() -> User:
    """Pick the first existing user as the test subject."""
    async with get_session() as session:
        user = (await session.execute(select(User).order_by(User.id).limit(1))).scalar_one_or_none()
        if user is None:
            raise RuntimeError("No users in DB — cannot run integration tests")
        return user


async def _dispose_engine() -> None:
    """Drop pooled connections. Must be called before asyncio.run() closes the loop
    so the next test starts with a fresh pool."""
    await engine.dispose()


async def _cleanup(user_id: int) -> None:
    """Remove any rows created by these tests."""
    async with get_session() as session:
        # delete dependent rows first
        await session.execute(delete(CalendarEvent).where(and_(
            CalendarEvent.user_id == user_id,
            CalendarEvent.description.ilike(f"%{TEST_MARKER}%"),
        )))
        await session.execute(delete(ScheduledReminder).where(and_(
            ScheduledReminder.user_id == user_id,
            ScheduledReminder.message.ilike(f"%{TEST_MARKER}%"),
        )))
        await session.execute(delete(AutopilotNotification).where(and_(
            AutopilotNotification.user_id == user_id,
            AutopilotNotification.body.ilike(f"%{TEST_MARKER}%"),
        )))
        # find test objectives by description and cascade
        test_objs = (await session.execute(select(Objective).where(and_(
            Objective.user_id == user_id,
            Objective.description.ilike(f"%{TEST_MARKER}%"),
        )))).scalars().all()
        for obj in test_objs:
            await session.execute(delete(Task).where(Task.objective_id == obj.id))
            await session.execute(delete(KeyResult).where(KeyResult.objective_id == obj.id))
            # routines may be linked via KR — delete by title marker
        # routines created by the test draft have title starting with the marker
        await session.execute(delete(Routine).where(and_(
            Routine.user_id == user_id,
            Routine.title.ilike(f"%{TEST_MARKER}%"),
        )))
        for obj in test_objs:
            await session.delete(obj)
        await session.execute(delete(OKRProposalDraft).where(and_(
            OKRProposalDraft.user_id == user_id,
            OKRProposalDraft.source_text.ilike(f"%{TEST_MARKER}%"),
        )))


async def _make_draft(user_id: int, payload: dict) -> int:
    """Create + accept a proposal draft. Returns draft.id."""
    async with get_session() as session:
        draft = OKRProposalDraft(
            user_id=user_id,
            source_text=f"{TEST_MARKER} synthetic proposal",
            draft_payload=payload,
            status="accepted",
        )
        session.add(draft)
        await session.flush()
        return draft.id


def _build_payload_with_due_tasks() -> dict:
    """A payload that produces 3 tasks with due_days 1/3/7 + 1 weekly routine."""
    return {
        "objective": {
            "title": f"{TEST_MARKER} Cardio Q",
            "category": "fitness",
            "description": f"{TEST_MARKER} synthetic objective",
            "priority_weight": 5,
        },
        "key_results": [
            {"title": "3x Cardio pro Woche", "metric_type": "number",
             "target_value": 12, "unit": "Sessions", "frequency": "weekly"},
        ],
        "tasks": [
            {"title": f"{TEST_MARKER} Schuhe besorgen", "due_days": 1, "priority": 2},
            {"title": f"{TEST_MARKER} Erste Cardio-Session", "due_days": 3, "priority": 2},
            {"title": f"{TEST_MARKER} Trainer fragen", "due_days": 7, "priority": 3},
        ],
        "routines": [
            {"title": f"{TEST_MARKER} Cardio", "frequency": "Mo/Mi/Fr",
             "time_of_day": "morning", "kr_title": "Cardio"},
        ],
    }


# ─── Tests ────────────────────────────────────────────────────────────────────

@requires_db
def test_execute_creates_calendar_events_for_tasks_with_due_date() -> None:
    """Each task with a due_date must produce exactly one deadline CalendarEvent."""
    async def run() -> None:
        user = await _get_test_user()
        await _cleanup(user.id)
        try:
            draft_id = await _make_draft(user.id, _build_payload_with_due_tasks())
            async with get_session() as session:
                draft = (await session.execute(
                    select(OKRProposalDraft).where(OKRProposalDraft.id == draft_id)
                )).scalar_one()
                result = await execute_accepted_proposal(session, draft)

            assert len(result.task_ids) == 3, f"expected 3 tasks, got {len(result.task_ids)}"

            async with get_session() as session:
                # Each of the 3 tasks should have exactly 1 deadline event
                deadline_events = (await session.execute(
                    select(CalendarEvent).where(and_(
                        CalendarEvent.user_id == user.id,
                        CalendarEvent.event_type == "deadline",
                        CalendarEvent.linked_task_id.in_(result.task_ids),
                    ))
                )).scalars().all()
                assert len(deadline_events) == 3, (
                    f"expected 3 deadline events for tasks with due_date, "
                    f"got {len(deadline_events)}"
                )
                # Every deadline event must have linked_task_id set
                for ev in deadline_events:
                    assert ev.linked_task_id in result.task_ids
        finally:
            await _cleanup(user.id)
            await _dispose_engine()

    asyncio.run(run())


@requires_db
def test_execute_creates_calendar_events_for_routines() -> None:
    """Routines must expand to CalendarEvent rows (Mo/Mi/Fr × 4 weeks = 12 events)."""
    async def run() -> None:
        user = await _get_test_user()
        await _cleanup(user.id)
        try:
            draft_id = await _make_draft(user.id, _build_payload_with_due_tasks())
            async with get_session() as session:
                draft = (await session.execute(
                    select(OKRProposalDraft).where(OKRProposalDraft.id == draft_id)
                )).scalar_one()
                await execute_accepted_proposal(session, draft)

            async with get_session() as session:
                # Find the test routine
                routines = (await session.execute(
                    select(Routine).where(and_(
                        Routine.user_id == user.id,
                        Routine.title.ilike(f"%{TEST_MARKER}%"),
                    ))
                )).scalars().all()
                assert len(routines) == 1, f"expected 1 routine, got {len(routines)}"
                routine = routines[0]

                events = (await session.execute(
                    select(CalendarEvent).where(and_(
                        CalendarEvent.user_id == user.id,
                        CalendarEvent.linked_routine_id == routine.id,
                        CalendarEvent.event_type == "routine",
                    ))
                )).scalars().all()
                # Mo/Mi/Fr × 4 weeks = 12 expected, but the count varies depending
                # on what weekday "today" is. Require at least ~9 (worst case).
                assert len(events) >= 9, (
                    f"expected ≥9 routine events (Mo/Mi/Fr × 4 weeks), got {len(events)}"
                )
                # All events must be linked to the routine
                assert all(ev.linked_routine_id == routine.id for ev in events)
        finally:
            await _cleanup(user.id)
            await _dispose_engine()

    asyncio.run(run())


@requires_db
def test_e2e_payload_to_calendar_events_total() -> None:
    """End-to-end: the result.calendar_event_ids must reflect tasks + routine expansion."""
    async def run() -> None:
        user = await _get_test_user()
        await _cleanup(user.id)
        try:
            draft_id = await _make_draft(user.id, _build_payload_with_due_tasks())
            async with get_session() as session:
                draft = (await session.execute(
                    select(OKRProposalDraft).where(OKRProposalDraft.id == draft_id)
                )).scalar_one()
                result = await execute_accepted_proposal(session, draft)

            # 3 task-deadlines reported directly + slot candidates + (routines are
            # created via life_planner which is post-commit, so not in result list,
            # but they must exist in DB).
            assert len(result.calendar_event_ids) >= 3, (
                "result.calendar_event_ids must include the 3 task-deadline events"
            )

            async with get_session() as session:
                # Count: events linked to this draft's tasks OR to its routines.
                # Routine events don't carry TEST_MARKER in description; they carry
                # linked_routine_id pointing to the test routine.
                test_routines = (await session.execute(
                    select(Routine).where(and_(
                        Routine.user_id == user.id,
                        Routine.title.ilike(f"%{TEST_MARKER}%"),
                    ))
                )).scalars().all()
                test_routine_ids = [r.id for r in test_routines]

                task_evt_count = len((await session.execute(
                    select(CalendarEvent.id).where(and_(
                        CalendarEvent.user_id == user.id,
                        CalendarEvent.linked_task_id.in_(result.task_ids or [0]),
                    ))
                )).scalars().all())
                routine_evt_count = len((await session.execute(
                    select(CalendarEvent.id).where(and_(
                        CalendarEvent.user_id == user.id,
                        CalendarEvent.linked_routine_id.in_(test_routine_ids or [0]),
                    ))
                )).scalars().all())
                total = task_evt_count + routine_evt_count
                # 3 task-deadlines + routine expansion (≥9 in 4 weeks of Mo/Mi/Fr)
                assert total >= 12, (
                    f"expected ≥12 events (3 task-deadlines + ≥9 routine), "
                    f"got {total} (tasks={task_evt_count} routines={routine_evt_count})"
                )
        finally:
            await _cleanup(user.id)
            await _dispose_engine()

    asyncio.run(run())
