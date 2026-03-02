"""Telegram slash command handlers — /settings, /toggle, /times, /status, etc."""
import logging
from typing import Optional

from telegram import Update
from telegram.ext import ContextTypes

from bot.core.shopping import get_shopping_summary
from bot.core.user_settings import (
    format_settings,
    get_or_create_user,
    toggle_setting,
    update_setting,
    BOOLEAN_TOGGLES,
    TIME_SETTINGS,
)
from bot.database.connection import get_session
from bot.telegram.sender import send_message

logger = logging.getLogger(__name__)

TOGGLE_ALIASES = {
    "priorities": "priorities_enabled",
    "review": "review_enabled",
    "proactive": "proactive_enabled",
    "reflection": "reflection_enabled",
}


async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command."""
    if not update.message or not update.effective_user:
        return
    tg_user = update.effective_user
    chat_id = update.message.chat_id

    async with get_session() as session:
        user = await get_or_create_user(session, tg_user.id, tg_user.username, tg_user.first_name)
        await session.commit()
        name = user.first_name or "Chef"

    await send_message(
        chat_id,
        f"👋 Hallo {name}! Ich bin dein persönlicher COO.\n\n"
        "Schick mir alles — Gedanken, Ziele, Fortschritte, Workouts, Einkäufe.\n"
        "Ich ordne alles ein und halte dich auf Kurs.\n\n"
        "Los geht's. Was willst du erreichen?",
    )


async def handle_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command."""
    if not update.message:
        return
    chat_id = update.message.chat_id
    text = (
        "🤖 *Personal OS — Was ich verstehe*\n\n"
        "**Ziele & OKRs:**\n"
        "  'Ich will gesünder leben' → Objective\n"
        "  '3L Wasser täglich' → Key Result\n\n"
        "**Tasks:**\n"
        "  'Steuern machen' → Task erstellen\n"
        "  'Fertig' / 'Done' → Task erledigen\n\n"
        "**Einkaufen:**\n"
        "  'Milch kaufen' → Einkaufsliste\n"
        "  'Einkaufen erledigt' → Alle abhaken\n\n"
        "**Logging:**\n"
        "  'Bankdrücken 80kg×8' → Workout\n"
        "  '1.5L Wasser' → Wasser\n"
        "  'Mood heute 7/10' → Stimmung\n\n"
        "**Routinen:**\n"
        "  'Jeden Morgen meditieren' → Routine\n\n"
        "**Termine:**\n"
        "  'Mittwoch 14 Uhr Zahnarzt' → Kalender\n\n"
        "**Befehle:**\n"
        "  /settings — Einstellungen\n"
        "  /toggle priorities|review|proactive|reflection\n"
        "  /times morning HH:MM | /times evening HH:MM\n"
        "  /status — Tagesübersicht\n"
        "  /shopping — Einkaufsliste\n"
        "  /ical — Kalender-Feed URL\n"
    )
    await send_message(chat_id, text)


async def handle_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /settings command — show all toggles."""
    if not update.message or not update.effective_user:
        return
    tg_user = update.effective_user
    chat_id = update.message.chat_id

    async with get_session() as session:
        user = await get_or_create_user(session, tg_user.id, tg_user.username, tg_user.first_name)
        await session.commit()
        settings = user.settings or {}

    await send_message(chat_id, format_settings(settings))


async def handle_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /toggle <setting> command.
    Usage: /toggle priorities | /toggle review | /toggle proactive | /toggle reflection
    """
    if not update.message or not update.effective_user:
        return
    tg_user = update.effective_user
    chat_id = update.message.chat_id

    args = context.args or []
    if not args:
        await send_message(
            chat_id,
            "❌ Bitte angeben was togglen:\n"
            "/toggle priorities\n"
            "/toggle review\n"
            "/toggle proactive\n"
            "/toggle reflection",
        )
        return

    toggle_arg = args[0].lower()
    setting_key = TOGGLE_ALIASES.get(toggle_arg)
    if not setting_key:
        await send_message(
            chat_id,
            f"❌ Unbekannte Einstellung: '{toggle_arg}'\n"
            "Gültig: priorities, review, proactive, reflection",
        )
        return

    async with get_session() as session:
        user = await get_or_create_user(session, tg_user.id, tg_user.username, tg_user.first_name)
        _, new_value = await toggle_setting(session, user.id, setting_key)
        await session.commit()

    label_map = {
        "priorities_enabled": "Prioritäten",
        "review_enabled": "Abend-Review",
        "proactive_enabled": "Proaktiv",
        "reflection_enabled": "Weekly Reflection",
    }
    label = label_map.get(setting_key, setting_key)
    status = "✅ AN" if new_value else "❌ AUS"
    await send_message(chat_id, f"⚙️ *{label}*: {status}")


async def handle_times(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /times command.
    Usage: /times — show times
           /times morning HH:MM — set morning brief time
           /times evening HH:MM — set evening review time
    """
    if not update.message or not update.effective_user:
        return
    tg_user = update.effective_user
    chat_id = update.message.chat_id

    args = context.args or []

    if not args:
        # Show current times
        async with get_session() as session:
            user = await get_or_create_user(session, tg_user.id, tg_user.username, tg_user.first_name)
            await session.commit()
            s = user.settings or {}
        text = (
            "⏰ *Eingestellte Zeiten*\n\n"
            f"☀️ Morning Brief: {s.get('morning_brief_time', '06:30')}\n"
            f"🌙 Evening Review: {s.get('evening_review_time', '21:00')}\n"
            f"🔮 Reflection: Sonntag {s.get('weekly_reflection_time', '19:00')}\n"
            f"🛒 Shopping-Reminder: {s.get('shopping_reminder_day', 'saturday')} {s.get('shopping_reminder_time', '10:00')}\n\n"
            "Ändern mit:\n"
            "/times morning 07:00\n"
            "/times evening 21:30"
        )
        await send_message(chat_id, text)
        return

    if len(args) < 2:
        await send_message(chat_id, "Nutzung: /times morning HH:MM oder /times evening HH:MM")
        return

    time_type = args[0].lower()
    time_value = args[1]

    # Validate time format
    try:
        h, m = time_value.split(":")
        assert 0 <= int(h) <= 23 and 0 <= int(m) <= 59
    except (ValueError, AssertionError):
        await send_message(chat_id, f"❌ Ungültiges Zeitformat: '{time_value}'. Bitte HH:MM verwenden.")
        return

    key_map = {
        "morning": "morning_brief_time",
        "evening": "evening_review_time",
    }
    setting_key = key_map.get(time_type)
    if not setting_key:
        await send_message(chat_id, "❌ Bitte 'morning' oder 'evening' angeben.")
        return

    async with get_session() as session:
        user = await get_or_create_user(session, tg_user.id, tg_user.username, tg_user.first_name)
        await update_setting(session, user.id, setting_key, time_value)
        await session.commit()

    label = "Morning Brief" if time_type == "morning" else "Evening Review"
    await send_message(chat_id, f"✅ {label} Zeit gesetzt auf: *{time_value}*")


async def handle_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /status command — quick overview of today."""
    if not update.message or not update.effective_user:
        return
    tg_user = update.effective_user
    chat_id = update.message.chat_id

    async with get_session() as session:
        from sqlalchemy import and_, select
        from datetime import date, datetime
        from bot.database.models import Task, Routine, RoutineCompletion, Objective, Log

        user = await get_or_create_user(session, tg_user.id, tg_user.username, tg_user.first_name)
        await session.commit()

        today = date.today()
        today_start = datetime.combine(today, datetime.min.time())

        # Active objectives count
        obj_result = await session.execute(
            select(Objective).where(and_(Objective.user_id == user.id, Objective.status == "active"))
        )
        obj_count = len(obj_result.scalars().all())

        # Open tasks count (non-shopping)
        task_result = await session.execute(
            select(Task).where(and_(
                Task.user_id == user.id,
                Task.status.in_(["todo", "in_progress"]),
                Task.category != "shopping",
            ))
        )
        open_tasks = task_result.scalars().all()
        task_count = len(open_tasks)

        # Shopping items
        shop_result = await session.execute(
            select(Task).where(and_(
                Task.user_id == user.id,
                Task.category == "shopping",
                Task.status == "todo",
            ))
        )
        shop_count = len(shop_result.scalars().all())

        # Routines done today
        routine_result = await session.execute(
            select(Routine).where(and_(Routine.user_id == user.id, Routine.status == "active"))
        )
        all_routines = routine_result.scalars().all()

        comp_result = await session.execute(
            select(RoutineCompletion.routine_id).where(and_(
                RoutineCompletion.user_id == user.id,
                RoutineCompletion.completed_at >= today_start,
            ))
        )
        done_routine_ids = set(comp_result.scalars().all())
        routines_done = len(done_routine_ids)
        routines_total = len(all_routines)

        # Water today
        water_result = await session.execute(
            select(Log).where(and_(
                Log.user_id == user.id,
                Log.log_type == "water",
                Log.logged_at >= today_start,
            ))
        )
        water_logs = water_result.scalars().all()
        water_total = sum(l.data.get("amount", 0) for l in water_logs)

    next_tasks = "\n".join(f"  {i+1}. {t.title}" for i, t in enumerate(open_tasks[:3]))
    text = (
        f"📊 *Status — {today.strftime('%d.%m.%Y')}*\n\n"
        f"🎯 Aktive Ziele: {obj_count}\n"
        f"📝 Offene Tasks: {task_count}\n"
        f"🛒 Einkaufsliste: {shop_count} Items\n"
        f"✅ Routinen: {routines_done}/{routines_total}\n"
        f"💧 Wasser heute: {water_total:.1f}L\n"
    )
    if next_tasks:
        text += f"\n📋 Nächste Tasks:\n{next_tasks}"

    await send_message(chat_id, text)


async def handle_shopping(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /shopping command — show current shopping list."""
    if not update.message or not update.effective_user:
        return
    tg_user = update.effective_user
    chat_id = update.message.chat_id

    async with get_session() as session:
        user = await get_or_create_user(session, tg_user.id, tg_user.username, tg_user.first_name)
        await session.commit()
        summary = await get_shopping_summary(session, user.id)

    await send_message(chat_id, summary)


async def handle_token(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /token command — generate and send API token for dashboard."""
    if not update.message or not update.effective_user:
        return
    tg_user = update.effective_user
    chat_id = update.message.chat_id

    async with get_session() as session:
        user = await get_or_create_user(session, tg_user.id, tg_user.username, tg_user.first_name)
        from bot.api.auth import generate_api_token
        token = await generate_api_token(session, user)
        await session.commit()

    await send_message(
        chat_id,
        f"🔑 *Dein Dashboard Token:*\n\n"
        f"`{token}`\n\n"
        "Öffne http://95.111.252.176:3000 und füge den Token ein.\n\n"
        "_Dieser Token gibt Zugriff auf dein Dashboard. Teile ihn nicht mit anderen._",
    )
    # Second message: plain text only so it's easy to copy on mobile
    await send_message(chat_id, token)


async def handle_organize(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /organize command — assign orphaned tasks to objectives via GPT-4o."""
    if not update.message or not update.effective_user:
        return
    tg_user = update.effective_user
    chat_id = update.message.chat_id

    await send_message(chat_id, "🤖 Analysiere deine Daten… Das kann 30–60 Sekunden dauern.")

    from bot.scripts.organize_data import organize_user_data
    async with get_session() as session:
        user = await get_or_create_user(session, tg_user.id, tg_user.username, tg_user.first_name)
        try:
            report = await organize_user_data(session, user)
            await session.commit()
        except Exception as e:
            logger.exception("organize_data failed for user %s", tg_user.id)
            await send_message(chat_id, f"❌ Fehler beim Organisieren: {e}")
            return

    lines = [
        "✅ *Daten organisiert!*\n",
        f"📌 Tasks zugeordnet: {report['orphaned_tasks_assigned']}",
        f"🎯 Neue Objectives: {report['new_objectives_created']}",
        f"💡 Tasks vorgeschlagen: {report['suggested_tasks_added']}",
    ]
    if report["details"]:
        lines.append("\n*Details:*")
        for d in report["details"][:15]:
            lines.append(f"  • {d}")
        if len(report["details"]) > 15:
            lines.append(f"  … und {len(report['details']) - 15} weitere")
    await send_message(chat_id, "\n".join(lines))


async def handle_ical(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /ical command — show iCal feed URL."""
    if not update.message or not update.effective_user:
        return
    tg_user = update.effective_user
    chat_id = update.message.chat_id

    async with get_session() as session:
        user = await get_or_create_user(session, tg_user.id, tg_user.username, tg_user.first_name)
        await session.commit()
        token = (user.settings or {}).get("ical_token", "")

    from bot.config import settings as app_settings
    base_url = app_settings.telegram_webhook_url.replace("/webhook/telegram", "")
    ical_url = f"{base_url}/cal/{token}.ics"

    await send_message(
        chat_id,
        f"📅 *iCal Feed*\n\n"
        f"Diese URL in Google/Apple Calendar einbinden:\n"
        f"`{ical_url}`\n\n"
        "Der Feed enthält alle deine Kalender-Events.",
    )
