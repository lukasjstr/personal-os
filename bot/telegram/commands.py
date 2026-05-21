"""Telegram slash command handlers — /settings, /toggle, /times, /status, etc."""
import logging
from typing import Optional

from telegram import Update
from telegram.ext import ContextTypes

from bot.core.goal_onboarding import cancel_onboarding, start_onboarding
from bot.core.objectives import (
    list_active_objectives as _list_active_objectives,
    pause_objective_for_cut,
    suggest_objective_to_cut,
)
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
from bot.telegram.sender import send_message, send_typing

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
        "  /goal — Geführtes Ziel-Coaching starten\n"
        "  /plan — Heutigen Tagesplan mit Konflikten anzeigen\n"
        "  /woche — Wochenübersicht + Konflikte anzeigen\n"
        "  /next — Bester nächster Schritt\n"
        "  /status — Tagesübersicht\n"
        "  /settings — Einstellungen\n"
        "  /toggle priorities|review|proactive|reflection\n"
        "  /times morning HH:MM | /times evening HH:MM\n"
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
    """Handle /token command — return (or reset) API token for dashboard.

    /token      → returns existing token (same every time)
    /token neu  → rotates to a fresh token
    """
    if not update.message or not update.effective_user:
        return
    tg_user = update.effective_user
    chat_id = update.message.chat_id

    args = context.args or []
    force_new = len(args) > 0 and args[0].lower() in ("neu", "reset", "new")

    async with get_session() as session:
        user = await get_or_create_user(session, tg_user.id, tg_user.username, tg_user.first_name)
        from bot.api.auth import generate_api_token
        token = await generate_api_token(session, user, force_new=force_new)
        await session.commit()

    note = "_(Neuer Token generiert)_\n\n" if force_new else "_(Dein Token bleibt immer gleich — einmal einrichten, fertig)_\n\n"
    await send_message(
        chat_id,
        f"🔑 *Dein Dashboard Token:*\n\n"
        f"`{token}`\n\n"
        f"{note}"
        "Öffne http://95.111.252.176:3000 und füge den Token ein.\n"
        "Tipp: Als PWA zum Homescreen hinzufügen → bleibt dauerhaft eingeloggt.\n\n"
        "_Token teilen = Zugriff auf dein Dashboard. Nicht weitergeben._",
    )
    # Second message: plain token for easy copy on mobile
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


async def handle_next(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /next command — show single best next action with inline done/skip buttons."""
    if not update.message or not update.effective_user:
        return
    tg_user = update.effective_user

    async with get_session() as session:
        user = await get_or_create_user(session, tg_user.id, tg_user.username, tg_user.first_name)
        await session.commit()

        from bot.core.next_action import send_next_action
        await send_next_action(context.bot, user, session)


async def handle_learn(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /learn command — show due learning items for spaced repetition review."""
    if not update.message or not update.effective_user:
        return
    tg_user = update.effective_user
    chat_id = update.message.chat_id

    async with get_session() as session:
        from bot.core.user_settings import get_or_create_user as _get_user
        from bot.core.knowledge import get_due_reviews
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup

        user = await _get_user(session, tg_user.id, tg_user.username, tg_user.first_name)
        await session.commit()

        due_items = await get_due_reviews(session, user.id)

    if not due_items:
        await send_message(
            chat_id,
            "📚 *Keine fälligen Wiederholungen!*\n\nAlles ist up to date. Gut gemacht! 🎉",
        )
        return

    # Show first due item with review buttons
    item = due_items[0]
    remaining = len(due_items)

    content_preview = ""
    if item.ai_summary:
        content_preview = f"\n\n📝 _{item.ai_summary[:300]}_"
    elif item.content:
        content_preview = f"\n\n_{item.content[:300]}_"

    text = (
        f"📚 *{item.title}*\n"
        f"Typ: {item.item_type} | Level: {'⭐' * item.skill_level}\n"
        f"Wiederholung #{item.review_count + 1}"
        f"{content_preview}\n\n"
        f"_{remaining} Item{'s' if remaining > 1 else ''} fällig_\n\n"
        "Wie gut erinnerst du dich?"
    )

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("😔 Schlecht", callback_data=f"learn_review_{item.id}_1"),
            InlineKeyboardButton("🆗 Ok", callback_data=f"learn_review_{item.id}_3"),
            InlineKeyboardButton("😊 Gut", callback_data=f"learn_review_{item.id}_4"),
            InlineKeyboardButton("🌟 Sehr gut", callback_data=f"learn_review_{item.id}_5"),
        ]
    ])

    if update.message:
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)


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


async def handle_goal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /goal command — start a conversational goal onboarding.

    Usage:
        /goal Ich will gesünder leben
        /goal cancel
        /goal  (no text → show help)
    """
    if not update.message or not update.effective_user:
        return

    tg_user = update.effective_user
    chat_id = update.message.chat_id
    text = (update.message.text or "").strip()

    # Extract goal text after /goal
    goal_text = text.split(maxsplit=1)[1] if len(text.split(maxsplit=1)) > 1 else ""

    # No text → show help
    if not goal_text:
        await send_message(
            chat_id,
            "🎯 *Ziel-Coaching starten*\n\n"
            "Schreib dein Ziel nach dem Befehl:\n"
            "`/goal Ich will gesünder leben`\n\n"
            "Oder schreib einfach dein Ziel — ich erkenne es automatisch!",
        )
        return

    # Cancel
    if goal_text.lower() in ("cancel", "abbrechen", "stop"):
        async with get_session() as session:
            user = await get_or_create_user(session, tg_user.id, tg_user.username, tg_user.first_name)
            cancelled = await cancel_onboarding(session, user.id)
            await session.commit()
        if cancelled:
            await send_message(chat_id, "❌ Ziel-Onboarding abgebrochen.")
        else:
            await send_message(chat_id, "Kein aktives Onboarding zum Abbrechen.")
        return

    # Start onboarding
    await send_typing(chat_id)

    async with get_session() as session:
        user = await get_or_create_user(session, tg_user.id, tg_user.username, tg_user.first_name)
        onboarding, intro = await start_onboarding(session, user.id, goal_text)
        await session.commit()

    await send_message(chat_id, intro)


async def handle_plan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/plan — Show today's calendar plan with conflict detection."""
    if not update.message or not update.effective_user:
        return
    tg_user = update.effective_user
    chat_id = update.message.chat_id

    await send_typing(chat_id)

    from bot.telegram.sender import get_bot
    from bot.core.plan_coherence import get_day_events, detect_conflicts, format_day_plan
    from datetime import date
    from zoneinfo import ZoneInfo

    async with get_session() as session:
        user = await get_or_create_user(session, tg_user.id, tg_user.username, tg_user.first_name)
        today = date.today()
        events = await get_day_events(session, user.id, today)
        if not events:
            await send_message(chat_id, "📅 Heute keine Events im Kalender.")
            return
        conflicts = detect_conflicts(events)
        text = format_day_plan(today, events, conflicts)

    await send_message(chat_id, text)


async def handle_woche(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/woche — Show this week's calendar overview with conflict detection."""
    if not update.message or not update.effective_user:
        return
    tg_user = update.effective_user
    chat_id = update.message.chat_id

    await send_typing(chat_id)

    from bot.core.plan_coherence import get_day_events, detect_conflicts, format_week_overview
    from datetime import date, timedelta

    async with get_session() as session:
        user = await get_or_create_user(session, tg_user.id, tg_user.username, tg_user.first_name)
        today = date.today()
        # Start from Monday of the current week
        week_start = today - timedelta(days=today.weekday())
        days_events = {}
        all_conflicts = []
        for i in range(7):
            day = week_start + timedelta(days=i)
            days_events[day] = await get_day_events(session, user.id, day)
            all_conflicts.extend(detect_conflicts(days_events[day]))

    text = format_week_overview(week_start, days_events)
    if all_conflicts:
        conflict_lines = ["\n⚠️ *Konflikte diese Woche:*"]
        for c in all_conflicts[:5]:
            conflict_lines.append(c["msg"])
        text += "\n" + "\n".join(conflict_lines)

    await send_message(chat_id, text)


# ─── V3 P11 — /review_q + /confirm_q commands ────────────────────────────────


async def handle_review_q(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/review_q — show the latest quarterly review."""
    if not update.message or not update.effective_user:
        return
    tg_user = update.effective_user
    chat_id = update.message.chat_id

    from bot.core.quarterly_review import format_quarterly_review_for_telegram
    from bot.database.models import QuarterlyReview
    from sqlalchemy import select as _select

    async with get_session() as session:
        user = await get_or_create_user(session, tg_user.id, tg_user.username, tg_user.first_name)
        review = (await session.execute(
            _select(QuarterlyReview).where(QuarterlyReview.user_id == user.id)
            .order_by(QuarterlyReview.generated_at.desc()).limit(1)
        )).scalar_one_or_none()
        if review is None:
            await send_message(chat_id, "Noch kein Quarterly-Review generiert.")
            return
        text = await format_quarterly_review_for_telegram(review)
        await send_message(chat_id, text)


async def handle_confirm_q(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/confirm_q — sign off the latest pending quarterly review."""
    if not update.message or not update.effective_user:
        return
    tg_user = update.effective_user
    chat_id = update.message.chat_id

    from bot.core.quarterly_review import confirm_quarterly_review
    from bot.database.models import QuarterlyReview
    from sqlalchemy import and_, select as _select

    async with get_session() as session:
        user = await get_or_create_user(session, tg_user.id, tg_user.username, tg_user.first_name)
        latest = (await session.execute(
            _select(QuarterlyReview).where(and_(
                QuarterlyReview.user_id == user.id,
                QuarterlyReview.completed_at == None,  # noqa: E711
            )).order_by(QuarterlyReview.generated_at.desc()).limit(1)
        )).scalar_one_or_none()
        if latest is None:
            await send_message(chat_id, "Kein offener Quarterly-Review zum Abschließen.")
            return
        reflection = " ".join(context.args) if context.args else None
        result = await confirm_quarterly_review(session, user.id, latest.id, reflection)
        if result is None:
            await send_message(chat_id, "Konnte den Review nicht abschließen.")
            return
        await session.commit()
        await send_message(
            chat_id,
            f"Q-Review {result.quarter_label} abgeschlossen.",
        )


# ─── V3 P08 — /cut command ────────────────────────────────────────────────────


async def handle_cut(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/cut <objective_id> — pause an active objective (expansion guard).

    /cut without args → list active objectives + suggested cut candidate.
    """
    if not update.message or not update.effective_user:
        return
    tg_user = update.effective_user
    chat_id = update.message.chat_id

    async with get_session() as session:
        user = await get_or_create_user(session, tg_user.id, tg_user.username, tg_user.first_name)

        if not context.args:
            data = await _list_active_objectives(session, user.id)
            if data["count"] == 0:
                await send_message(chat_id, "Keine aktiven Objectives.")
                return
            cut = await suggest_objective_to_cut(session, user.id)
            lines = [f"Aktive Objectives ({data['count']}):"]
            for o in data["objectives"]:
                stale = f" · {o['stale_days']}d stale" if o["stale_days"] is not None else ""
                lines.append(f"  #{o['id']} {o['title']} [{o['category']}]{stale}")
            if cut:
                lines.append("")
                lines.append(
                    f"Schwächstes: #{cut['id']} '{cut['title']}' "
                    f"({cut['days_stale']}d ohne Log, {int(cut['completion']*100)}% erfüllt)"
                )
                lines.append(f"Cut: /cut {cut['id']}")
            await send_message(chat_id, "\n".join(lines))
            return

        try:
            target_id = int(context.args[0])
        except ValueError:
            await send_message(chat_id, "Format: /cut <id>  (Objective- oder Task-ID)")
            return

        # Try Objective first (P08 semantics). Fall through to Task (P09 semantics).
        obj = await pause_objective_for_cut(session, user.id, target_id)
        if obj is not None:
            await send_message(chat_id, f"Objective pausiert: #{obj.id} {obj.title}")
            return

        from bot.core.friday_cut import cut_task
        task = await cut_task(session, user.id, target_id)
        if task is not None:
            await send_message(chat_id, f"Task gestrichen: #{task.id} {task.title}")
            return

        await send_message(chat_id, f"#{target_id} nicht gefunden (weder Objective noch Task).")
