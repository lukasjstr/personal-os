"""Evening review cron job — sends daily summary at 21:00."""
import logging
from datetime import date, datetime

from openai import AsyncOpenAI
from sqlalchemy import and_, select

from bot.ai.context import build_context
from bot.ai.prompts import EVENING_REVIEW_PROMPT
from bot.config import settings
from bot.database.connection import get_session
from bot.database.models import Log, Routine, RoutineCompletion, Task, User
from bot.telegram.sender import send_message

logger = logging.getLogger(__name__)

openai_client = AsyncOpenAI(api_key=settings.openai_api_key)


async def send_evening_review() -> None:
    """Send evening review to all active users."""
    logger.info("Running evening review job")
    async with get_session() as session:
        result = await session.execute(select(User))
        users = result.scalars().all()

    for user in users:
        try:
            await _send_review_to_user(user)
        except Exception as e:
            logger.exception("Evening review failed for user %s: %s", user.id, e)


async def _send_review_to_user(user: User) -> None:
    """Generate and send evening review to a specific user."""
    today = date.today()
    today_start = datetime.combine(today, datetime.min.time())

    async with get_session() as session:
        context = await build_context(session, user)

        # Today's completed tasks
        done_result = await session.execute(
            select(Task).where(
                and_(
                    Task.user_id == user.id,
                    Task.status == "done",
                    Task.completed_at >= today_start,
                )
            )
        )
        done_tasks = done_result.scalars().all()

        # Today's open tasks
        open_result = await session.execute(
            select(Task).where(
                and_(Task.user_id == user.id, Task.status.in_(["todo", "in_progress"]))
            )
        )
        open_tasks = open_result.scalars().all()

        # Routine completions today
        routine_result = await session.execute(select(Routine).where(Routine.user_id == user.id))
        routines = routine_result.scalars().all()
        comp_result = await session.execute(
            select(RoutineCompletion.routine_id).where(
                and_(
                    RoutineCompletion.user_id == user.id,
                    RoutineCompletion.completed_at >= today_start,
                )
            )
        )
        completed_routine_ids = set(comp_result.scalars().all())

        # Water today
        water_result = await session.execute(
            select(Log).where(
                and_(Log.user_id == user.id, Log.log_type == "water", Log.logged_at >= today_start)
            )
        )
        water_logs = water_result.scalars().all()
        total_water = sum(l.data.get("amount", 0) for l in water_logs)

    summary_parts = []
    if done_tasks:
        summary_parts.append(f"Erledigte Tasks: {', '.join(t.title for t in done_tasks)}")
    if open_tasks:
        summary_parts.append(f"Offene Tasks: {', '.join(t.title for t in open_tasks[:5])}")
    if routines:
        routine_summary = []
        for r in routines:
            status = "✅" if r.id in completed_routine_ids else "⚠️"
            routine_summary.append(f"{status} {r.title}")
        summary_parts.append("Routinen: " + ", ".join(routine_summary))
    if total_water > 0:
        summary_parts.append(f"Wasser heute: {total_water:.1f}L")

    user_summary = "\n".join(summary_parts) if summary_parts else "Keine Aktivitäten heute geloggt."

    response = await openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": EVENING_REVIEW_PROMPT},
            {"role": "user", "content": f"Kontext:\n{context}\n\nHeutiger Status:\n{user_summary}"},
        ],
        max_tokens=600,
        temperature=0.5,
    )
    review = response.choices[0].message.content or ""
    await send_message(user.telegram_id, f"🌙 Tages-Review\n\n{review}")
    logger.info("Evening review sent to user %s", user.id)
