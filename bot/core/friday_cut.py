"""V3 P09 — Friday-Cut: force an explicit weekly cut decision.

Sent every Friday 17:00 Berlin. Lukas must reply with either a task id
(`/cut 123` or just `123`) or free text. The reply path is in
bot/telegram/handler.py:handle_text and the pending-state is in
bot/core/smart_detector._pending_prompts (type="friday_cut").
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import BrainDump, Task, WeeklyPriority

logger = logging.getLogger(__name__)


async def build_friday_cut_prompt(
    session: AsyncSession, user_id: int, today: Optional[date] = None
) -> str:
    """Return the Coach-Modus Friday-Cut message for one user."""
    if today is None:
        today = date.today()
    week_start = today - timedelta(days=today.weekday())

    prios = (await session.execute(
        select(WeeklyPriority).where(and_(
            WeeklyPriority.user_id == user_id,
            WeeklyPriority.week_start >= week_start,
        )).order_by(WeeklyPriority.priority_rank.asc())
    )).scalars().all()

    untouched = await _get_untouched_priority_tasks(session, user_id, today, week_start)

    lines: list[str] = ["━━ FREITAG-CUT ━━", ""]
    if prios:
        lines.append("Diese Woche Top-Prios:")
        for p in prios:
            mark = "✓" if p.status == "completed" else "·"
            lines.append(f"  {mark} {p.title}")
        lines.append("")

    if untouched:
        lines.append("Offen / unbearbeitet:")
        for t in untouched[:6]:
            lines.append(f"  · #{t.id} {t.title}")
        lines.append("")

    lines.append("JETZT: Was streichst du? Eine Sache wandert in Brain Dump.")
    lines.append("Antworte mit Task-ID, mit `/cut <id>`, oder mit Text der Sache die weg soll.")
    return "\n".join(lines)


async def _get_untouched_priority_tasks(
    session: AsyncSession, user_id: int, today: date, week_start: date
) -> list[Task]:
    """Tasks created this week or earlier, still todo/in_progress, not touched."""
    return list((await session.execute(
        select(Task).where(and_(
            Task.user_id == user_id,
            Task.status.in_(["todo", "in_progress"]),
            Task.category != "shopping",
            Task.created_at <= datetime.combine(today, datetime.max.time()),
        )).order_by(Task.priority.asc()).limit(10)
    )).scalars().all())


async def cut_task(
    session: AsyncSession, user_id: int, task_id: int, *, archive_to_braindump: bool = True
) -> Optional[Task]:
    """Cancel a task, set cancelled_reason='friday_cut', archive to brain_dumps."""
    task = (await session.execute(
        select(Task).where(and_(Task.id == task_id, Task.user_id == user_id))
    )).scalar_one_or_none()
    if task is None:
        return None
    task.status = "cancelled"
    task.cancelled_reason = "friday_cut"
    task.cancelled_at = datetime.utcnow()
    if archive_to_braindump:
        session.add(BrainDump(
            user_id=user_id,
            raw_input=f"[friday_cut_archive] {task.title}",
            processed=True,
            ai_interpretation=(
                f"Friday-Cut: Task#{task_id} '{task.title}' wurde am "
                f"{date.today().isoformat()} explizit gestrichen statt weiter geschleppt."
            ),
        ))
    await session.flush()
    return task


async def cut_free_text(session: AsyncSession, user_id: int, text: str) -> BrainDump:
    """Free-text cut: park it in brain_dumps with the friday_cut_archive tag."""
    dump = BrainDump(
        user_id=user_id,
        raw_input=f"[friday_cut_archive] {text.strip()[:1000]}",
        processed=True,
        ai_interpretation=(
            f"Friday-Cut (Freitext): am {date.today().isoformat()} explizit gestrichen."
        ),
    )
    session.add(dump)
    await session.flush()
    return dump


async def count_cuts_this_week(
    session: AsyncSession, user_id: int, today: Optional[date] = None
) -> int:
    """Cuts during the current ISO week (Mon..Sun)."""
    if today is None:
        today = date.today()
    week_start = datetime.combine(today - timedelta(days=today.weekday()), datetime.min.time())
    week_end = week_start + timedelta(days=7)
    n = (await session.execute(
        select(Task).where(and_(
            Task.user_id == user_id,
            Task.cancelled_reason == "friday_cut",
            Task.cancelled_at >= week_start,
            Task.cancelled_at < week_end,
        ))
    )).scalars().all()
    return len(n)
