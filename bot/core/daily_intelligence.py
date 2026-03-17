"""Daily Intelligence flows for Personal OS Telegram bot.

Implements:
- Morning context collection (energy, time, focus) via inline buttons
- Evening check-in (task completion + win of day + gap analysis)
- Streak risk alerts for stale objectives
- Daily plan formatting and delivery
"""
from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta
from typing import Optional

from openai import AsyncOpenAI
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup

from bot.config import settings
from bot.database.connection import get_session
from bot.database.models import DailyContext, EveningCheckin, Objective, Task, User

logger = logging.getLogger(__name__)
openai_client = AsyncOpenAI(api_key=settings.openai_api_key)

# ── In-memory state for multi-step inline flows ────────────────────────────────
# { user_id: { "step": "energy"|"time"|"focus", "energy": int, "hours": float } }
_morning_ctx_state: dict[int, dict] = {}

# { user_id: { "task_ids": [int], "selected_ids": set(), "checkin_date": date } }
_evening_ci_state: dict[int, dict] = {}


# ── Morning context collection ─────────────────────────────────────────────────

async def collect_morning_context(bot: Bot, user: User, session: AsyncSession) -> None:
    """Send the first morning context question (energy) via inline buttons.

    Only sends if no DailyContext exists yet for today.
    """
    today = date.today()
    existing = await session.execute(
        select(DailyContext).where(
            DailyContext.user_id == user.id,
            DailyContext.date == today,
        )
    )
    if existing.scalar_one_or_none() is not None:
        logger.debug("Morning context already collected for user %s", user.id)
        return

    _morning_ctx_state[user.id] = {"step": "energy"}

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⚡ Hoch (8-10)", callback_data="ctx_energy_high"),
            InlineKeyboardButton("⚙️ Mittel (5-7)", callback_data="ctx_energy_mid"),
            InlineKeyboardButton("😴 Niedrig (1-4)", callback_data="ctx_energy_low"),
        ]
    ])
    try:
        await bot.send_message(
            chat_id=user.telegram_id,
            text="☀️ Kurze Lagemeldung:\n\nEnergie heute? 🔋",
            reply_markup=keyboard,
        )
    except Exception:
        logger.exception("Failed to send morning context question to user %s", user.id)


async def handle_ctx_energy(bot: Bot, user: User, callback_data: str) -> None:
    """Handle energy callback; store and ask time available."""
    energy_map = {
        "ctx_energy_high": 9,
        "ctx_energy_mid": 6,
        "ctx_energy_low": 3,
    }
    energy = energy_map.get(callback_data, 6)
    state = _morning_ctx_state.setdefault(user.id, {})
    state["energy"] = energy
    state["step"] = "time"

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🕐 < 2h", callback_data="ctx_time_2"),
            InlineKeyboardButton("🕒 2-4h", callback_data="ctx_time_4"),
            InlineKeyboardButton("🕔 4-6h", callback_data="ctx_time_6"),
            InlineKeyboardButton("🕗 6h+", callback_data="ctx_time_8"),
        ]
    ])
    try:
        await bot.send_message(
            chat_id=user.telegram_id,
            text="Wieviel Zeit hast du heute? ⏳",
            reply_markup=keyboard,
        )
    except Exception:
        logger.exception("Failed to send time question to user %s", user.id)


async def handle_ctx_time(bot: Bot, user: User, callback_data: str) -> None:
    """Handle time callback; store and ask focus area."""
    time_map = {
        "ctx_time_2": 1.5,
        "ctx_time_4": 3.0,
        "ctx_time_6": 5.0,
        "ctx_time_8": 7.0,
    }
    hours = time_map.get(callback_data, 3.0)
    state = _morning_ctx_state.setdefault(user.id, {})
    state["hours"] = hours
    state["step"] = "focus"

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("💼 Business", callback_data="ctx_focus_business"),
            InlineKeyboardButton("❤️ Personal", callback_data="ctx_focus_personal"),
        ],
        [
            InlineKeyboardButton("💪 Fitness", callback_data="ctx_focus_fitness"),
            InlineKeyboardButton("💰 Finance", callback_data="ctx_focus_finance"),
        ],
        [
            InlineKeyboardButton("📚 Learning", callback_data="ctx_focus_learning"),
            InlineKeyboardButton("🏥 Health", callback_data="ctx_focus_health"),
        ],
        [
            InlineKeyboardButton("🚫 Kein Fokus", callback_data="ctx_focus_none"),
        ],
    ])
    try:
        await bot.send_message(
            chat_id=user.telegram_id,
            text="Wo liegt heute dein Fokus? 🎯",
            reply_markup=keyboard,
        )
    except Exception:
        logger.exception("Failed to send focus question to user %s", user.id)


async def handle_ctx_focus(bot: Bot, user: User, session: AsyncSession, callback_data: str) -> None:
    """Handle focus callback; save DailyContext and send daily plan."""
    focus_map = {
        "ctx_focus_business": "business",
        "ctx_focus_personal": "personal",
        "ctx_focus_fitness": "fitness",
        "ctx_focus_finance": "finance",
        "ctx_focus_learning": "learning",
        "ctx_focus_health": "health",
        "ctx_focus_none": None,
    }
    focus_area = focus_map.get(callback_data)
    state = _morning_ctx_state.pop(user.id, {})
    energy = state.get("energy", 6)
    hours_available = state.get("hours", 3.0)

    today = date.today()

    # Upsert DailyContext
    existing_result = await session.execute(
        select(DailyContext).where(
            DailyContext.user_id == user.id,
            DailyContext.date == today,
        )
    )
    ctx = existing_result.scalar_one_or_none()
    if ctx is None:
        ctx = DailyContext(user_id=user.id, date=today)
        session.add(ctx)

    ctx.energy = energy
    ctx.hours_available = hours_available
    ctx.focus_area = focus_area
    await session.flush()

    # Generate daily plan
    try:
        daily_plan = await _generate_daily_plan(session, user, ctx)
        ctx.daily_plan = daily_plan
        await session.flush()
        await send_daily_plan_message(bot, user, daily_plan)
    except Exception:
        logger.exception("Failed to generate daily plan for user %s", user.id)
        try:
            await bot.send_message(
                chat_id=user.telegram_id,
                text="✅ Kontext gespeichert! Dein Plan für heute ist bereit — viel Erfolg! 💪",
            )
        except Exception:
            logger.exception("Failed to send fallback context confirmation to user %s", user.id)


# ── Evening check-in ───────────────────────────────────────────────────────────

async def send_evening_checkin(bot: Bot, user: User, session: AsyncSession) -> None:
    """Send evening check-in with today's top tasks as inline buttons."""
    today = date.today()
    today_start = datetime.combine(today, datetime.min.time())
    today_end = datetime.combine(today, datetime.max.time())

    # Fetch top open/in-progress tasks (or tasks completed today, if any)
    tasks_result = await session.execute(
        select(Task).where(and_(
            Task.user_id == user.id,
            Task.status.in_(["todo", "in_progress"]),
            Task.category != "shopping",
        )).order_by(Task.priority.asc()).limit(5)
    )
    tasks = tasks_result.scalars().all()

    # Also include tasks completed today so we can show accurate check-in
    done_result = await session.execute(
        select(Task).where(and_(
            Task.user_id == user.id,
            Task.status == "done",
            Task.completed_at >= today_start,
            Task.completed_at <= today_end,
            Task.category != "shopping",
        )).order_by(Task.priority.asc()).limit(5)
    )
    done_today = done_result.scalars().all()

    # Combine: open tasks first, then completed today (deduplicated)
    shown_tasks = list(tasks)
    shown_ids = {t.id for t in shown_tasks}
    for t in done_today:
        if t.id not in shown_ids:
            shown_tasks.append(t)
            shown_ids.add(t.id)
    shown_tasks = shown_tasks[:5]

    if not shown_tasks:
        try:
            await bot.send_message(
                chat_id=user.telegram_id,
                text="🌙 Guten Abend! Keine offenen Tasks heute — schön, wenn alles erledigt ist. 🎉\n\nWas war dein Gewinn des Tages?",
            )
        except Exception:
            logger.exception("Failed to send empty evening check-in to user %s", user.id)
        return

    # Store state
    task_ids = [t.id for t in shown_tasks]
    _evening_ci_state[user.id] = {
        "task_ids": task_ids,
        "selected_ids": set(),
        "checkin_date": today,
        "step": "tasks",
    }

    # Build task list text
    task_lines = "\n".join(f"○ {t.title}" for t in shown_tasks)
    text = f"🌙 Abend-Check-in — wie war dein Tag?\n\nDeine heutigen Top-Tasks waren:\n{task_lines}\n\nWas hast du erledigt?"

    # Build inline buttons
    buttons = [
        [InlineKeyboardButton(f"☐ {t.title[:30]}", callback_data=f"ci_task_{t.id}")]
        for t in shown_tasks
    ]
    buttons.append([
        InlineKeyboardButton("✅ Alles erledigt", callback_data="ci_all"),
        InlineKeyboardButton("❌ Nichts erledigt", callback_data="ci_none"),
    ])
    keyboard = InlineKeyboardMarkup(buttons)

    try:
        await bot.send_message(
            chat_id=user.telegram_id,
            text=text,
            reply_markup=keyboard,
        )
    except Exception:
        logger.exception("Failed to send evening check-in to user %s", user.id)


async def handle_ci_task_toggle(
    bot: Bot, user: User, session: AsyncSession, callback_data: str
) -> None:
    """Toggle a task in the evening check-in selection."""
    state = _evening_ci_state.get(user.id)
    if not state:
        return

    task_id = int(callback_data.replace("ci_task_", ""))
    selected = state["selected_ids"]
    if task_id in selected:
        selected.discard(task_id)
    else:
        selected.add(task_id)

    # Acknowledge and show current selection
    selected_count = len(selected)
    try:
        await bot.send_message(
            chat_id=user.telegram_id,
            text=f"✅ {selected_count} Task(s) markiert. Drücke 'Alles erledigt' oder wähle weitere Tasks. Wenn fertig, tippe einfach deinen Gewinn des Tages.",
        )
    except Exception:
        logger.exception("Failed to send ci_task_toggle ack to user %s", user.id)


async def handle_ci_none(bot: Bot, user: User, session: AsyncSession) -> None:
    """Mark 0 tasks done, proceed to win-of-day question."""
    state = _evening_ci_state.get(user.id, {})
    state["selected_ids"] = set()
    state["step"] = "win"
    _evening_ci_state[user.id] = state

    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("⏭ Überspringen", callback_data="ci_skip_win"),
    ]])
    try:
        await bot.send_message(
            chat_id=user.telegram_id,
            text="Verstanden — manchmal läuft der Tag einfach anders. 💪\n\nWas war dein *Gewinn des Tages*? (Freitext oder überspringen)",
            reply_markup=keyboard,
        )
    except Exception:
        logger.exception("Failed to send ci_none message to user %s", user.id)


async def handle_ci_all(bot: Bot, user: User, session: AsyncSession) -> None:
    """Mark all planned tasks done, proceed to win-of-day question."""
    state = _evening_ci_state.get(user.id, {})
    task_ids = state.get("task_ids", [])
    state["selected_ids"] = set(task_ids)
    state["step"] = "win"
    _evening_ci_state[user.id] = state

    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("⏭ Überspringen", callback_data="ci_skip_win"),
    ]])
    try:
        await bot.send_message(
            chat_id=user.telegram_id,
            text=f"🔥 Stark! Alle {len(task_ids)} Tasks erledigt!\n\nWas war dein *Gewinn des Tages*? (Freitext oder überspringen)",
            reply_markup=keyboard,
        )
    except Exception:
        logger.exception("Failed to send ci_all message to user %s", user.id)


async def handle_ci_win_text(bot: Bot, user: User, session: AsyncSession, text: str) -> bool:
    """Handle free-text win-of-day answer. Returns True if it consumed the message."""
    state = _evening_ci_state.get(user.id)
    if not state or state.get("step") != "win":
        return False

    win_text = text if text.lower() not in ("überspringen", "skip", "-") else None
    await _finish_evening_checkin(bot, user, session, win_text)
    return True


async def handle_ci_skip_win(bot: Bot, user: User, session: AsyncSession) -> None:
    """Skip the win-of-day question."""
    await _finish_evening_checkin(bot, user, session, win_text=None)


async def _finish_evening_checkin(
    bot: Bot, user: User, session: AsyncSession, win_text: Optional[str]
) -> None:
    """Save EveningCheckin and send gap analysis."""
    state = _evening_ci_state.pop(user.id, {})
    today = state.get("checkin_date", date.today())
    task_ids = state.get("task_ids", [])
    selected_ids = list(state.get("selected_ids", set()))

    # Upsert EveningCheckin
    existing_result = await session.execute(
        select(EveningCheckin).where(
            EveningCheckin.user_id == user.id,
            EveningCheckin.date == today,
        )
    )
    checkin = existing_result.scalar_one_or_none()
    if checkin is None:
        checkin = EveningCheckin(user_id=user.id, date=today)
        session.add(checkin)

    checkin.tasks_planned = len(task_ids)
    checkin.tasks_completed = len(selected_ids)
    checkin.completed_task_ids = selected_ids
    checkin.win_of_day = win_text
    await session.flush()

    # Generate gap analysis
    try:
        gap = await _generate_gap_analysis(session, user, checkin, task_ids, selected_ids)
        checkin.gap_analysis = gap
        await session.flush()
        gap_text = _format_gap_analysis(gap, win_text)
        await bot.send_message(chat_id=user.telegram_id, text=gap_text)
    except Exception:
        logger.exception("Failed to generate gap analysis for user %s", user.id)
        try:
            await bot.send_message(
                chat_id=user.telegram_id,
                text=f"✅ Check-in gespeichert! {len(selected_ids)}/{len(task_ids)} Tasks erledigt. Gute Nacht! 🌙",
            )
        except Exception:
            logger.exception("Failed to send fallback gap message to user %s", user.id)


# ── Streak risk alerts ─────────────────────────────────────────────────────────

async def send_streak_risk_alerts(bot: Bot, session: AsyncSession) -> None:
    """Check all active users for stale objectives and send streak risk alerts."""
    users_result = await session.execute(
        select(User).where(User.is_active == True)  # noqa: E712
    )
    users = users_result.scalars().all()

    for user in users:
        try:
            await _check_and_alert_streak_risks(bot, user, session)
        except Exception:
            logger.exception("Failed streak risk check for user %s", user.id)


async def _check_and_alert_streak_risks(
    bot: Bot, user: User, session: AsyncSession
) -> None:
    """Find stale objectives and alert the user with a quick-win suggestion."""
    today = date.today()
    stale_cutoff = datetime.combine(today - timedelta(days=3), datetime.min.time())

    objs_result = await session.execute(
        select(Objective).where(and_(
            Objective.user_id == user.id,
            Objective.status == "active",
        )).order_by(Objective.priority_weight.desc().nullslast()).limit(10)
    )
    objectives = objs_result.scalars().all()

    for obj in objectives:
        # Check if any related task was completed in the last 3 days
        recent_done = await session.execute(
            select(Task).where(and_(
                Task.user_id == user.id,
                Task.objective_id == obj.id,
                Task.status == "done",
                Task.completed_at >= stale_cutoff,
            )).limit(1)
        )
        if recent_done.scalar_one_or_none() is not None:
            continue  # recent activity — no alert needed

        # Find a quick-win task (lowest priority number, open)
        quick_win_result = await session.execute(
            select(Task).where(and_(
                Task.user_id == user.id,
                Task.objective_id == obj.id,
                Task.status.in_(["todo", "in_progress"]),
            )).order_by(Task.priority.asc()).limit(1)
        )
        quick_win = quick_win_result.scalar_one_or_none()

        # Calculate days since last activity
        last_dt = obj.updated_at or obj.created_at
        days_stale = (datetime.utcnow() - last_dt).days if last_dt else 3

        quick_win_line = f"\n\n💡 Quick Win: {quick_win.title}" if quick_win else ""
        task_id_suffix = f"\n\nci_task_{quick_win.id}" if quick_win else ""

        buttons = []
        if quick_win:
            buttons.append([
                InlineKeyboardButton(
                    "✅ Als erledigt markieren",
                    callback_data=f"ci_task_{quick_win.id}",
                ),
            ])
        buttons.append([
            InlineKeyboardButton(
                "📋 Alle Tasks anzeigen",
                callback_data=f"streak_view_{obj.id}",
            ),
        ])
        keyboard = InlineKeyboardMarkup(buttons)

        text = (
            f"⚠️ *{obj.title}* hat seit {days_stale} Tagen keine Bewegung."
            f"{quick_win_line}"
        )
        try:
            await bot.send_message(
                chat_id=user.telegram_id,
                text=text,
                reply_markup=keyboard,
            )
        except Exception:
            logger.exception(
                "Failed to send streak alert for objective %s to user %s", obj.id, user.id
            )


# ── Daily plan generation & formatting ────────────────────────────────────────

async def send_daily_plan_message(bot: Bot, user: User, daily_plan: dict) -> None:
    """Format and send the daily plan as a structured Telegram message."""
    text = _format_daily_plan(daily_plan)
    try:
        await bot.send_message(chat_id=user.telegram_id, text=text)
    except Exception:
        logger.exception("Failed to send daily plan to user %s", user.id)


def _format_daily_plan(plan: dict) -> str:
    """Format the daily plan dict into a human-readable Telegram message."""
    number_emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]
    lines = ["🎯 Dein Plan für heute:\n"]

    tasks = plan.get("tasks", [])
    for i, task in enumerate(tasks[:5]):
        num = number_emojis[i] if i < len(number_emojis) else f"{i+1}."
        title = task.get("title", "Task")
        reason = task.get("reason", "")
        minutes = task.get("minutes")
        duration_str = f" (~{minutes} min)" if minutes else ""
        lines.append(f"{num} {title}")
        if reason:
            lines.append(f"   → {reason}{duration_str}")
        lines.append("")

    focus_block = plan.get("focus_block")
    if focus_block:
        start = focus_block.get("suggested_start", "")
        duration = focus_block.get("duration_min", "")
        desc = focus_block.get("description", "")
        time_str = f"{start} Uhr" if start else ""
        dur_str = f" ({duration} min)" if duration else ""
        lines.append(f"⏰ Focus Block: {time_str}{dur_str}")
        if desc:
            lines.append(f"   {desc}")
        lines.append("")

    kickoff = plan.get("motivational_kickoff", "")
    if kickoff:
        lines.append(f"💪 {kickoff}")

    return "\n".join(lines).strip()


async def _generate_daily_plan(
    session: AsyncSession, user: User, ctx: DailyContext
) -> dict:
    """Call GPT-4o to generate a personalized daily plan based on context."""
    today = date.today()

    tasks_result = await session.execute(
        select(Task).where(and_(
            Task.user_id == user.id,
            Task.status.in_(["todo", "in_progress"]),
            Task.category != "shopping",
        )).order_by(Task.priority.asc()).limit(10)
    )
    tasks = tasks_result.scalars().all()

    task_lines = "\n".join(
        f"- P{t.priority}: {t.title}"
        + (f" [fällig: {t.due_date}]" if t.due_date else "")
        + (f" [{t.category}]" if t.category else "")
        for t in tasks
    )

    energy_desc = {9: "hoch (8-10)", 6: "mittel (5-7)", 3: "niedrig (1-4)"}.get(
        ctx.energy or 6, str(ctx.energy)
    )
    focus_str = ctx.focus_area or "kein spezifischer Fokus"

    prompt = f"""Du bist der persönliche COO von {user.first_name or "Chef"}.

TAGES-KONTEXT:
- Energie: {energy_desc}
- Verfügbare Zeit: {ctx.hours_available or 3}h
- Fokus-Bereich: {focus_str}
- Datum: {today.strftime("%d.%m.%Y")}

OFFENE TASKS:
{task_lines or "Keine Tasks vorhanden."}

Erstelle einen optimierten Tagesplan. Antworte NUR mit validem JSON:

{{
  "tasks": [
    {{
      "title": "<Task-Titel>",
      "reason": "<kurze Begründung warum jetzt>",
      "minutes": <geschätzte Minuten als Zahl>
    }}
  ],
  "focus_block": {{
    "suggested_start": "<HH:MM>",
    "duration_min": <Minuten als Zahl>,
    "description": "<kurze Beschreibung des Focus Blocks>"
  }},
  "motivational_kickoff": "<motivierender Abschlusssatz, 1 Satz>"
}}

Wähle maximal 3 Tasks, passend zu Energie und verfügbarer Zeit. Priorisiere den gewählten Fokus-Bereich.
"""

    try:
        response = await openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=600,
            temperature=0.5,
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content or "{}"
        return json.loads(raw)
    except Exception:
        logger.exception("GPT daily plan generation failed for user %s", user.id)
        # Fallback: top 3 tasks as plain plan
        fallback_tasks = [
            {"title": t.title, "reason": "hohe Priorität", "minutes": 45}
            for t in tasks[:3]
        ]
        return {
            "tasks": fallback_tasks,
            "motivational_kickoff": "Los geht's — du schaffst das! 💪",
        }


# ── Gap analysis ───────────────────────────────────────────────────────────────

async def _generate_gap_analysis(
    session: AsyncSession,
    user: User,
    checkin: EveningCheckin,
    planned_ids: list[int],
    completed_ids: list[int],
) -> dict:
    """Call GPT-4o to generate a gap analysis and tomorrow prep."""
    planned_result = await session.execute(
        select(Task).where(Task.id.in_(planned_ids))
    )
    planned_tasks = {t.id: t for t in planned_result.scalars().all()}

    completed_titles = [
        planned_tasks[tid].title for tid in completed_ids if tid in planned_tasks
    ]
    missed_titles = [
        planned_tasks[tid].title
        for tid in planned_ids
        if tid not in completed_ids and tid in planned_tasks
    ]

    tomorrow_open_result = await session.execute(
        select(Task).where(and_(
            Task.user_id == user.id,
            Task.status.in_(["todo", "in_progress"]),
            Task.category != "shopping",
        )).order_by(Task.priority.asc()).limit(5)
    )
    tomorrow_tasks = tomorrow_open_result.scalars().all()
    tomorrow_lines = "\n".join(f"- P{t.priority}: {t.title}" for t in tomorrow_tasks)

    win = checkin.win_of_day or "nicht angegeben"

    prompt = f"""Du bist der persönliche COO von {user.first_name or "Chef"}.

ABEND-CHECK-IN:
- Erledigt ({len(completed_titles)}): {", ".join(completed_titles) or "nichts"}
- Nicht erledigt ({len(missed_titles)}): {", ".join(missed_titles) or "nichts"}
- Gewinn des Tages: {win}

OFFENE TASKS FÜR MORGEN:
{tomorrow_lines or "Keine"}

Erstelle eine kurze Gap-Analyse. Antworte NUR mit validem JSON:

{{
  "summary": "<1-2 Sätze Zusammenfassung des Tages>",
  "gap_insight": "<Was blieb liegen und warum — nur wenn relevant, sonst null>",
  "tomorrow_top3": ["<Task 1>", "<Task 2>", "<Task 3>"],
  "closing_message": "<kurze motivierende Schlussnachricht>"
}}
"""
    try:
        response = await openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=400,
            temperature=0.6,
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content or "{}"
        return json.loads(raw)
    except Exception:
        logger.exception("GPT gap analysis failed for user %s", user.id)
        return {
            "summary": f"{len(completed_ids)}/{len(planned_ids)} Tasks erledigt.",
            "tomorrow_top3": [t.title for t in tomorrow_tasks[:3]],
            "closing_message": "Gute Nacht! Morgen weitermachen. 🌙",
        }


def _format_gap_analysis(gap: dict, win_text: Optional[str]) -> str:
    """Format gap analysis dict into a human-readable message."""
    lines = []

    summary = gap.get("summary", "")
    if summary:
        lines.append(summary)

    if win_text:
        lines.append(f"\n🏆 Gewinn des Tages: {win_text}")

    gap_insight = gap.get("gap_insight")
    if gap_insight:
        lines.append(f"\n📉 Gap: {gap_insight}")

    tomorrow = gap.get("tomorrow_top3", [])
    if tomorrow:
        lines.append("\n📋 Top Prioritäten morgen:")
        for i, t in enumerate(tomorrow[:3], 1):
            lines.append(f"  {i}. {t}")

    closing = gap.get("closing_message", "Gute Nacht! 🌙")
    lines.append(f"\n{closing}")

    return "\n".join(lines).strip()


# ── Scheduler-facing job wrappers ──────────────────────────────────────────────

async def run_morning_context_collection() -> None:
    """Scheduler job: send morning context questions to all active users."""
    from bot.telegram.sender import get_bot as _get_bot
    bot = _get_bot()

    async with get_session() as session:
        users_result = await session.execute(
            select(User).where(User.is_active == True)  # noqa: E712
        )
        users = users_result.scalars().all()

        for user in users:
            s = user.settings or {}
            if not s.get("priorities_enabled", True):
                continue
            try:
                await collect_morning_context(bot, user, session)
            except Exception:
                logger.exception("Morning context collection failed for user %s", user.id)


async def run_evening_checkin() -> None:
    """Scheduler job: send evening check-in to all active users."""
    from bot.telegram.sender import get_bot as _get_bot
    bot = _get_bot()

    async with get_session() as session:
        users_result = await session.execute(
            select(User).where(User.is_active == True)  # noqa: E712
        )
        users = users_result.scalars().all()

        for user in users:
            s = user.settings or {}
            if not s.get("review_enabled", True):
                continue
            try:
                await send_evening_checkin(bot, user, session)
            except Exception:
                logger.exception("Evening check-in failed for user %s", user.id)


async def run_streak_risk_check() -> None:
    """Scheduler job: check streak risks and alert users."""
    from bot.telegram.sender import get_bot as _get_bot
    bot = _get_bot()

    async with get_session() as session:
        await send_streak_risk_alerts(bot, session)
