"""Sprint 3: Weekly auto-plan — Monday morning, AI generates the week's task plan from lagging KRs."""
import logging
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from openai import AsyncOpenAI
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from bot.config import settings
from bot.database.connection import get_session
from bot.database.models import KeyResult, Objective, Task, User
from bot.telegram.sender import send_message

logger = logging.getLogger(__name__)
openai_client = AsyncOpenAI(api_key=settings.openai_api_key)


async def generate_weekly_plan_for_user(session: AsyncSession, user: User) -> dict | None:
    """Generate a weekly task plan from the user's lagging KRs. Returns plan dict."""
    import json as _json

    today = date.today()

    # Load active objectives + KRs + open tasks
    obj_res = await session.execute(
        select(Objective)
        .options(selectinload(Objective.key_results), selectinload(Objective.tasks))
        .where(and_(Objective.user_id == user.id, Objective.status == "active"))
    )
    objectives = obj_res.scalars().all()

    if not objectives:
        return None

    # Build KR summary sorted by lowest progress (most lagging first)
    kr_data = []
    for obj in objectives:
        for kr in obj.key_results:
            if kr.status == "completed":
                continue
            progress = (
                min(100, int((kr.current_value / kr.target_value) * 100))
                if kr.target_value and kr.target_value > 0 else 0
            )
            kr_data.append({
                "objective_id": obj.id,
                "objective_title": obj.title,
                "objective_category": obj.category,
                "kr_title": kr.title,
                "metric_type": kr.metric_type,
                "current": kr.current_value,
                "target": kr.target_value,
                "unit": kr.unit or "",
                "progress_pct": progress,
            })

    # Sort by progress ascending (most lagging first), take top 5
    kr_data.sort(key=lambda x: x["progress_pct"])
    top_lagging = kr_data[:5]

    if not top_lagging:
        return None

    next_monday = today + timedelta(days=(7 - today.weekday()) % 7 or 7)
    week_end = next_monday + timedelta(days=6)

    prompt = f"""Heute ist {today.isoformat()}. Die Woche läuft von {next_monday.isoformat()} bis {week_end.isoformat()}.

Die 5 Key Results mit dem größten Rückstand:
{_json.dumps(top_lagging, ensure_ascii=False, indent=2)}

Erstelle einen motivierenden, realistischen Wochenplan. Antworte NUR als JSON:
{{
  "week_theme": "Motivierendes Wochenmotto (max 60 Zeichen)",
  "weekly_commitment": "Eine konkrete Verpflichtung für diese Woche (1 Satz)",
  "daily_focus": [
    {{
      "day": "Montag",
      "objective_title": "Titel des Ziels",
      "task_title": "Konkreter Task für diesen Tag",
      "estimated_minutes": 45
    }}
  ],
  "key_priorities": [
    {{
      "kr_title": "KR-Titel",
      "why_urgent": "Warum jetzt wichtig (1 Satz)",
      "suggested_tasks": ["Task 1", "Task 2"]
    }}
  ]
}}

Regeln: Jeden Tag (Mo-So) einen fokussierten Task. Realistisch und konkret. Max 60-90 min pro Tag."""

    try:
        resp = await openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Du bist ein persönlicher Produktivitäts-Coach. Antworte auf Deutsch. Nur valides JSON."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.4,
            response_format={"type": "json_object"},
        )
        return _json.loads(resp.choices[0].message.content)
    except Exception as exc:
        logger.error("Weekly plan generation failed for user %d: %s", user.id, exc)
        return None


async def send_weekly_auto_plan() -> None:
    """Monday 07:30 job: generate and send the weekly plan to all active users."""
    now_berlin = datetime.now(tz=ZoneInfo("Europe/Berlin"))
    # Only run on Mondays
    if now_berlin.weekday() != 0:
        return

    async with get_session() as session:
        result = await session.execute(select(User).where(User.is_active == True))  # noqa: E712
        users = result.scalars().all()

        for user in users:
            try:
                plan = await generate_weekly_plan_for_user(session, user)
                if not plan:
                    continue

                # Format the weekly plan message
                theme = plan.get("week_theme", "Neue Woche, neue Chancen")
                commitment = plan.get("weekly_commitment", "")
                daily = plan.get("daily_focus", [])
                priorities = plan.get("key_priorities", [])

                days_text = ""
                for d in daily[:5]:  # Mon-Fri
                    day = d.get("day", "")
                    task = d.get("task_title", "")
                    mins = d.get("estimated_minutes", 0)
                    obj = d.get("objective_title", "")
                    days_text += f"\n*{day}*: {task} ({mins} min)\n   ↳ _{obj}_"

                prio_text = ""
                for p in priorities[:3]:
                    kr = p.get("kr_title", "")
                    why = p.get("why_urgent", "")
                    tasks = p.get("suggested_tasks", [])
                    prio_text += f"\n• *{kr}*\n  {why}"
                    if tasks:
                        prio_text += "\n  Tasks: " + " · ".join(tasks[:2])

                msg = (
                    f"📅 *Wochenplan — {theme}*\n\n"
                    f"💪 _{commitment}_\n"
                    f"\n*Dein Fokus diese Woche:*{days_text}"
                    f"\n\n*Top Prioritäten:*{prio_text}"
                    f"\n\nHab eine produktive Woche! 🚀"
                )

                await send_message(user.telegram_id, msg, parse_mode="Markdown")
                logger.info("Weekly plan sent to user %d", user.id)

            except Exception as exc:
                logger.error("Weekly plan send failed for user %d: %s", user.id, exc)
