"""V3 P07 — Reminder severity + escalation tests.

Requires PERSONAL_OS_DB_AVAILABLE=1.

Integration tests insert a test ScheduledReminder linked to a test Task
(marked with [v3-p07-test]) and verify the escalation sweep behaviour.
"""
import asyncio
import os
from datetime import datetime, timedelta

import pytest
from sqlalchemy import and_, delete, select

from bot.core.reminder_escalation import (
    ESCALATION_WINDOW_HOURS,
    determine_severity,
    get_flagged_escalations,
    is_acknowledged,
    run_escalation_sweep,
)
from bot.database.connection import engine, get_session
from bot.database.models import (
    ScheduledReminder,
    Task,
    User,
)


TEST_MARKER = "[v3-p07-test]"

requires_db = pytest.mark.skipif(
    not os.environ.get("PERSONAL_OS_DB_AVAILABLE"),
    reason="DB not available (set PERSONAL_OS_DB_AVAILABLE=1 to run)",
)


# ─── Pure tests (severity table constants) ────────────────────────────────────

def test_escalation_windows_defined() -> None:
    assert ESCALATION_WINDOW_HOURS["critical"] == 2
    assert ESCALATION_WINDOW_HOURS["important"] == 4
    assert ESCALATION_WINDOW_HOURS["normal"] == 0


# ─── Integration tests ────────────────────────────────────────────────────────


async def _get_user() -> User:
    async with get_session() as session:
        return (await session.execute(select(User).order_by(User.id).limit(1))).scalar_one()


async def _cleanup(user_id: int) -> None:
    async with get_session() as session:
        await session.execute(delete(ScheduledReminder).where(and_(
            ScheduledReminder.user_id == user_id,
            ScheduledReminder.message.ilike(f"%{TEST_MARKER}%"),
        )))
        await session.execute(delete(Task).where(and_(
            Task.user_id == user_id,
            Task.title.ilike(f"%{TEST_MARKER}%"),
        )))


@requires_db
def test_determine_severity_task_due_today_is_critical() -> None:
    from datetime import date

    async def run() -> None:
        user = await _get_user()
        await _cleanup(user.id)
        try:
            async with get_session() as session:
                task = Task(
                    user_id=user.id,
                    title=f"{TEST_MARKER} due-today",
                    status="todo",
                    due_date=date.today(),
                )
                session.add(task)
                await session.flush()
                sev = await determine_severity(session, user.id, linked_task_id=task.id)
                assert sev == "critical", f"expected critical, got {sev}"
        finally:
            await _cleanup(user.id)
            await engine.dispose()

    asyncio.run(run())


@requires_db
def test_determine_severity_unlinked_is_normal() -> None:
    async def run() -> None:
        try:
            async with get_session() as session:
                user = (await session.execute(select(User).order_by(User.id).limit(1))).scalar_one()
                sev = await determine_severity(session, user.id)
                assert sev == "normal"
        finally:
            await engine.dispose()

    asyncio.run(run())


@requires_db
def test_determine_severity_linked_only_is_important() -> None:
    """Linked to a task that's NOT due today → important, not critical."""
    from datetime import date

    async def run() -> None:
        user = await _get_user()
        await _cleanup(user.id)
        try:
            async with get_session() as session:
                task = Task(
                    user_id=user.id,
                    title=f"{TEST_MARKER} future",
                    status="todo",
                    due_date=date.today() + timedelta(days=30),
                )
                session.add(task)
                await session.flush()
                sev = await determine_severity(session, user.id, linked_task_id=task.id)
                assert sev == "important", f"expected important, got {sev}"
        finally:
            await _cleanup(user.id)
            await engine.dispose()

    asyncio.run(run())


@requires_db
def test_run_escalation_sweep_advances_ignored_critical_reminder() -> None:
    """A critical reminder sent ≥2h ago and not acknowledged must advance to step 1."""
    from datetime import date

    async def run() -> None:
        user = await _get_user()
        await _cleanup(user.id)
        try:
            async with get_session() as session:
                task = Task(
                    user_id=user.id,
                    title=f"{TEST_MARKER} reminder-target",
                    status="todo",
                    due_date=date.today(),
                )
                session.add(task)
                await session.flush()
                sent_at = datetime.utcnow() - timedelta(hours=3)
                reminder = ScheduledReminder(
                    user_id=user.id,
                    reminder_type="task_deadline",
                    message=f"{TEST_MARKER} Erinnerung — Status?",
                    scheduled_for=sent_at,
                    status="sent",
                    sent_at=sent_at,
                    severity="critical",
                    escalation_step=0,
                    linked_task_id=task.id,
                    auto_generated=True,
                )
                session.add(reminder)
                await session.flush()
                rid = reminder.id

            # Run sweep — patch out the Telegram sender to avoid network calls
            import bot.core.reminder_escalation as resc
            orig_send = resc._send_step1_nudge

            async def _stub_send(_session, _r):
                return None

            resc._send_step1_nudge = _stub_send  # type: ignore[assignment]
            try:
                async with get_session() as session:
                    counters = await run_escalation_sweep(session)
            finally:
                resc._send_step1_nudge = orig_send  # type: ignore[assignment]

            assert counters["checked"] >= 1
            assert counters["step_1"] >= 1

            async with get_session() as session:
                r = await session.get(ScheduledReminder, rid)
                assert r is not None
                assert r.escalation_step >= 1
        finally:
            await _cleanup(user.id)
            await engine.dispose()

    asyncio.run(run())


@requires_db
def test_run_escalation_sweep_skips_acknowledged_reminder() -> None:
    """Acknowledged reminder (task done) must NOT advance escalation_step."""
    from datetime import date

    async def run() -> None:
        user = await _get_user()
        await _cleanup(user.id)
        try:
            async with get_session() as session:
                task = Task(
                    user_id=user.id,
                    title=f"{TEST_MARKER} done-task",
                    status="done",
                    completed_at=datetime.utcnow() - timedelta(hours=1),
                    due_date=date.today(),
                )
                session.add(task)
                await session.flush()
                sent_at = datetime.utcnow() - timedelta(hours=3)
                reminder = ScheduledReminder(
                    user_id=user.id,
                    reminder_type="task_deadline",
                    message=f"{TEST_MARKER} acknowledged reminder",
                    scheduled_for=sent_at,
                    status="sent",
                    sent_at=sent_at,
                    severity="critical",
                    escalation_step=0,
                    linked_task_id=task.id,
                )
                session.add(reminder)
                await session.flush()
                rid = reminder.id

            async with get_session() as session:
                await run_escalation_sweep(session)

            async with get_session() as session:
                r = await session.get(ScheduledReminder, rid)
                assert r is not None
                assert r.escalation_step == 0, "ack reminder should not escalate"
        finally:
            await _cleanup(user.id)
            await engine.dispose()

    asyncio.run(run())


@requires_db
def test_get_flagged_escalations_returns_step2_plus() -> None:
    async def run() -> None:
        user = await _get_user()
        await _cleanup(user.id)
        try:
            async with get_session() as session:
                sent_at = datetime.utcnow() - timedelta(hours=6)
                reminder = ScheduledReminder(
                    user_id=user.id,
                    reminder_type="task_deadline",
                    message=f"{TEST_MARKER} step-2 reminder",
                    scheduled_for=sent_at,
                    status="sent",
                    sent_at=sent_at,
                    severity="critical",
                    escalation_step=2,
                )
                session.add(reminder)
                await session.flush()

            async with get_session() as session:
                flagged = await get_flagged_escalations(session, user.id, hours=24)
                assert len(flagged) >= 1
                assert any(TEST_MARKER in (r.message or "") for r in flagged)
        finally:
            await _cleanup(user.id)
            await engine.dispose()

    asyncio.run(run())
