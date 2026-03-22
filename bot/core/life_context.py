"""Life Context Layer — adapts the system to current life mode.

Modes:
  - normal:    Standard operation
  - travel:    Traveling — relax gym routines, adjust timezone expectations
  - sick:      Ill — reduce task load, add recovery focus, pause fitness
  - vacation:  On vacation — pause work reminders, minimal notifications
  - intense:   Sprint/focus mode — maximize productivity, block distractions
  - recovery:  Recovery phase — gentle reminders, focus on rest and health

Each mode modifies:
  - Task load (how many tasks shown in daily plan)
  - Routine skip tolerance (before flagging as missed)
  - Notification frequency
  - Morning brief tone and content
"""
from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Optional

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import LifeContext

logger = logging.getLogger(__name__)

MODE_CONFIG = {
    "normal": {
        "emoji": "⚡",
        "label": "Normal",
        "task_load": 5,                  # tasks shown in daily plan
        "routine_skip_tolerance": 2,      # days before flagging missed routine
        "notification_frequency": "normal",
        "morning_tone": "proaktiv",
        "fitness_active": True,
        "work_reminders": True,
    },
    "travel": {
        "emoji": "✈️",
        "label": "Reise",
        "task_load": 3,
        "routine_skip_tolerance": 7,
        "notification_frequency": "minimal",
        "morning_tone": "leicht",
        "fitness_active": False,
        "work_reminders": True,
    },
    "sick": {
        "emoji": "🤒",
        "label": "Krank",
        "task_load": 2,
        "routine_skip_tolerance": 14,
        "notification_frequency": "minimal",
        "morning_tone": "erholend",
        "fitness_active": False,
        "work_reminders": False,
    },
    "vacation": {
        "emoji": "🌴",
        "label": "Urlaub",
        "task_load": 1,
        "routine_skip_tolerance": 30,
        "notification_frequency": "off",
        "morning_tone": "entspannt",
        "fitness_active": False,
        "work_reminders": False,
    },
    "intense": {
        "emoji": "🔥",
        "label": "Intensiv-Phase",
        "task_load": 7,
        "routine_skip_tolerance": 1,
        "notification_frequency": "high",
        "morning_tone": "fokussiert",
        "fitness_active": True,
        "work_reminders": True,
    },
    "recovery": {
        "emoji": "🌿",
        "label": "Recovery",
        "task_load": 3,
        "routine_skip_tolerance": 5,
        "notification_frequency": "gentle",
        "morning_tone": "sanft",
        "fitness_active": False,
        "work_reminders": True,
    },
}


async def set_life_mode(
    session: AsyncSession,
    user_id: int,
    mode: str,
    notes: Optional[str] = None,
    active_until: Optional[date] = None,
) -> LifeContext:
    """Activate a new life mode, deactivating any previous active mode."""
    if mode not in MODE_CONFIG:
        raise ValueError(f"Unknown life mode: {mode}. Valid: {list(MODE_CONFIG.keys())}")

    # Deactivate all current active contexts
    current_contexts = (await session.execute(
        select(LifeContext).where(and_(
            LifeContext.user_id == user_id,
            LifeContext.is_active == True,  # noqa: E712
        ))
    )).scalars().all()
    for ctx in current_contexts:
        ctx.is_active = False

    ctx = LifeContext(
        user_id=user_id,
        mode=mode,
        notes=notes,
        active_from=date.today(),
        active_until=active_until,
        is_active=True,
    )
    session.add(ctx)
    await session.flush()
    logger.info("Life mode set: user=%d mode=%s until=%s", user_id, mode, active_until)
    return ctx


async def get_active_life_mode(session: AsyncSession, user_id: int) -> str:
    """Return the current active life mode key. Defaults to 'normal'."""
    ctx = (await session.execute(
        select(LifeContext).where(and_(
            LifeContext.user_id == user_id,
            LifeContext.is_active == True,  # noqa: E712
        )).order_by(LifeContext.created_at.desc()).limit(1)
    )).scalar_one_or_none()

    if ctx is None:
        return "normal"

    # Auto-expire if past active_until
    if ctx.active_until and ctx.active_until < date.today():
        ctx.is_active = False
        await session.flush()
        return "normal"

    return ctx.mode


async def get_life_mode_config(session: AsyncSession, user_id: int) -> dict:
    """Return the full configuration dict for the current life mode."""
    mode = await get_active_life_mode(session, user_id)
    config = MODE_CONFIG.get(mode, MODE_CONFIG["normal"]).copy()
    config["mode"] = mode
    return config


def get_morning_brief_prefix(mode: str) -> str:
    """Return a mode-specific greeting prefix for the morning brief."""
    prefixes = {
        "normal": "",
        "travel": "✈️ *Reise-Modus aktiv* — Heute nur das Wichtigste.\n\n",
        "sick": "🤒 *Krank-Modus aktiv* — Fokus auf Erholung. Bitte schon mal ruhig bleiben.\n\n",
        "vacation": "🌴 *Urlaubs-Modus aktiv* — Genieß deinen freien Tag!\n\n",
        "intense": "🔥 *Intensiv-Phase* — Volle Konzentration. Du schaffst das.\n\n",
        "recovery": "🌿 *Recovery-Modus aktiv* — Sanfter Start. Lass deinen Körper sich erholen.\n\n",
    }
    return prefixes.get(mode, "")


def get_task_load_limit(mode: str) -> int:
    """Return max tasks to show in daily plan for this mode."""
    return MODE_CONFIG.get(mode, MODE_CONFIG["normal"])["task_load"]


def format_life_mode_message(mode: str, notes: Optional[str] = None, active_until: Optional[date] = None) -> str:
    """Format a Telegram confirmation message for a life mode change."""
    config = MODE_CONFIG.get(mode, MODE_CONFIG["normal"])
    emoji = config["emoji"]
    label = config["label"]

    lines = [f"{emoji} *{label}-Modus aktiviert*"]

    mode_descriptions = {
        "normal": "Normalbetrieb wiederhergestellt.",
        "travel": "Gym-Routinen pausiert, Aufgabenlast reduziert, minimale Benachrichtigungen.",
        "sick": "Fitness pausiert, Work-Erinnerungen aus, Fokus auf Erholung.",
        "vacation": "Fast alle Benachrichtigungen aus. Genieß den Urlaub!",
        "intense": "Maximale Aufgabenlast, hohe Benachrichtigungsfrequenz, Fitness aktiv.",
        "recovery": "Sanfte Benachrichtigungen, reduzierte Aufgaben, Fitness pausiert.",
    }
    lines.append(mode_descriptions.get(mode, ""))

    if notes:
        lines.append(f"📝 {notes}")
    if active_until:
        lines.append(f"⏰ Automatisch bis {active_until.strftime('%d.%m.%Y')}")

    return "\n".join(lines)
