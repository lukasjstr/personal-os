"""Sprint 3: Daily streak risk check — alert users when an objective has stalled."""
import logging
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from bot.database.connection import get_session
from bot.database.models import Objective, Task, User
from bot.telegram.sender import send_message

logger = logging.getLogger(__name__)

STALL_DAYS = 3  # alert after this many days without a completed task
CATEGORY_EMOJI = {
    "health": "🏥", "fitness": "💪", "business": "💼",
    "personal": "🧠", "finance": "💰", "learning": "📚",
    "relationships": "❤️",
}


async def check_streak_risks_for_user(session: AsyncSession, user: User) -> list[dict]:
    """Return list of at-risk objectives for a user."""
    today = date.today()
    cutoff = datetime.combine(today - timedelta(days=STALL_DAYS), datetime.min.time())
    thirty_ago = datetime.combine(today - timedelta(days=30), datetime.min.time())

    obj_res = await session.execute(
        select(Objective)
        .options(selectinload(Objective.tasks))
        .where(and_(Objective.user_id == user.id, Objective.status == "active"))
    )
    objectives = obj_res.scalars().all()

    risks = []
    for obj in objectives:
        # Check last completed task
        last_done = max(
            (t.completed_at for t in obj.tasks if t.status == "done" and t.completed_at),
            default=None,
        )
        days_since = (today - last_done.date()).days if last_done else 999

        if days_since < STALL_DAYS:
            continue

        open_tasks = [t for t in obj.tasks if t.status not in ("done", "cancelled")]
        suggested = open_tasks[0].title if open_tasks else None

        risks.append({
            "objective_id": obj.id,
            "title": obj.title,
            "category": obj.category,
            "days_since": min(days_since, 999),
            "open_task_count": len(open_tasks),
            "suggested_action": suggested,
        })

    return sorted(risks, key=lambda r: r["days_since"], reverse=True)


async def send_streak_risk_alerts() -> None:
    """Daily 10:00 job: check for stalled objectives and send Telegram alerts."""
    async with get_session() as session:
        result = await session.execute(select(User).where(User.is_active == True))  # noqa: E712
        users = result.scalars().all()

        for user in users:
            try:
                risks = await check_streak_risks_for_user(session, user)
                if not risks:
                    continue

                # Only alert for the top 2 risks to avoid spam
                for risk in risks[:2]:
                    emoji = CATEGORY_EMOJI.get(risk["category"], "🎯")
                    days = risk["days_since"]
                    title = risk["title"]
                    suggested = risk["suggested_action"]
                    open_count = risk["open_task_count"]

                    if days >= 999:
                        days_text = "noch nie begonnen"
                    elif days == 1:
                        days_text = "seit gestern keine Aktivität"
                    else:
                        days_text = f"seit {days} Tagen keine Aktivität"

                    msg = f"⚠️ *{emoji} {title}*\n_{days_text}_"

                    if suggested:
                        msg += f"\n\n💡 Quick Win:\n*{suggested}*"

                    if open_count > 1:
                        msg += f"\n_{open_count} offene Tasks warten_"

                    msg += "\n\nKleine Schritte zählen — du schaffst das! 💪"

                    await send_message(user.telegram_id, msg, parse_mode="Markdown")
                    logger.info(
                        "Streak risk alert sent to user %d for objective %d (%d days stalled)",
                        user.id, risk["objective_id"], days,
                    )

            except Exception as exc:
                logger.error("Streak risk check failed for user %d: %s", user.id, exc)
