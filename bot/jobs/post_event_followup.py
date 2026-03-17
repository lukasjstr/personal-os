"""Post-event follow-up: fires 15 min after each calendar event ends.

Sends a contextual question with inline buttons based on event type and title
keywords. Uses ScheduledReminder to avoid duplicate follow-ups.
"""
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from bot.database.connection import get_session
from bot.database.models import CalendarEvent, ScheduledReminder, User
from bot.telegram.sender import get_bot

logger = logging.getLogger(__name__)

# Keywords in event title → follow-up config
# Format: (question, button_yes_text, callback_yes, button_no_text, callback_no)
_KEYWORD_MAP = [
    # Fitness / Training
    (
        ["training", "kraft", "push", "pull", "beine", "gym", "pumpen", "sport", "workout"],
        "💪 Hast du trainiert?",
        "✅ Ja, war gut!", "followup_workout_done",
        "❌ Nein, verschoben", "followup_workout_skip",
    ),
    # Cardio / Laufen
    (
        ["cardio", "laufen", "joggen", "run", "bike", "radfahren", "schritte"],
        "🏃 Cardio gemacht?",
        "✅ Ja, fertig!", "followup_cardio_done",
        "❌ Nein", "followup_cardio_skip",
    ),
    # Supplement / Routine
    (
        ["supplement", "vitamine", "omega", "kreatin", "magnesium"],
        "💊 Supplemente genommen?",
        "✅ Ja!", "followup_supp_done",
        "❌ Vergessen", "followup_supp_skip",
    ),
    # Essen / Ernährung
    (
        ["essen", "mahlzeit", "lunch", "frühstück", "abendessen", "meal", "food"],
        "🍽️ Was hast du gegessen?",
        "✍️ Jetzt eingeben", "followup_food_log",
        "⏭ Überspringen", "followup_food_skip",
    ),
    # Meeting / Gespräch
    (
        ["meeting", "gespräch", "call", "termin", "besprechung", "konferenz", "zoom"],
        "📞 Meeting war gut?",
        "✅ Produktiv", "followup_meeting_good",
        "📝 Notizen nötig", "followup_meeting_notes",
    ),
    # Lernen / Kurs
    (
        ["lernen", "kurs", "vorlesung", "lesen", "studieren", "lektüre", "buch", "kapitel"],
        "📚 Lerneinheit gemacht?",
        "✅ Ja, erledigt!", "followup_learn_done",
        "❌ Nicht geschafft", "followup_learn_skip",
    ),
    # Schlafen / Erholung
    (
        ["schlafen", "schlaf", "erholung", "ruhe", "nap", "power nap"],
        "😴 Ausgeruht gefühlt?",
        "✅ Ja, gut", "followup_sleep_good",
        "😵 Nein, müde", "followup_sleep_bad",
    ),
]

# Fallback for event_type
_TYPE_MAP = {
    "training": (
        "💪 Training beendet — hast du es gemacht?",
        "✅ Ja!", "followup_workout_done",
        "❌ Nein", "followup_workout_skip",
    ),
    "meeting": (
        "📞 Meeting vorbei — alles gut gelaufen?",
        "✅ Ja", "followup_meeting_good",
        "📝 Notizen", "followup_meeting_notes",
    ),
    "routine": (
        "🔁 Routine erledigt?",
        "✅ Ja!", "followup_routine_done",
        "❌ Nein", "followup_routine_skip",
    ),
    "deadline": (
        "⏰ Deadline — abgegeben?",
        "✅ Ja, fertig!", "followup_deadline_done",
        "⚠️ Noch offen", "followup_deadline_open",
    ),
}


def _build_followup(event: CalendarEvent) -> tuple[str, str, str, str, str] | None:
    """Return (question, yes_text, yes_cb, no_text, no_cb) or None if no match."""
    title_lower = event.title.lower()

    for keywords, question, yes_text, yes_cb, no_text, no_cb in _KEYWORD_MAP:
        if any(kw in title_lower for kw in keywords):
            return question, yes_text, yes_cb, no_text, no_cb

    fallback = _TYPE_MAP.get(event.event_type)
    if fallback:
        return fallback

    return None


async def process_post_event_followups() -> None:
    """Run every 15 minutes. Find events that ended 5–20 min ago and send follow-up."""
    now_berlin = datetime.now(tz=ZoneInfo("Europe/Berlin"))
    now_utc = now_berlin.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)

    window_start = now_utc - timedelta(minutes=20)
    window_end = now_utc - timedelta(minutes=5)
    today_start = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)

    async with get_session() as session:
        users_result = await session.execute(
            select(User).where(User.is_active == True)  # noqa: E712
        )
        users = users_result.scalars().all()

        for user in users:
            s = user.settings or {}
            if not s.get("proactive_enabled", True):
                continue

            try:
                await _check_user_followups(session, user, window_start, window_end, today_start)
            except Exception:
                logger.exception("Post-event followup error for user %s", user.id)


async def _check_user_followups(
    session: AsyncSession,
    user: User,
    window_start: datetime,
    window_end: datetime,
    today_start: datetime,
) -> None:
    """Send follow-up questions for events that just ended."""
    result = await session.execute(
        select(CalendarEvent).where(and_(
            CalendarEvent.user_id == user.id,
            CalendarEvent.end_time >= window_start,
            CalendarEvent.end_time <= window_end,
            CalendarEvent.all_day == False,  # noqa: E712
        ))
    )
    events = result.scalars().all()

    if not events:
        return

    bot = get_bot()

    for event in events:
        reminder_key = f"post_event_{event.id}"

        # Skip if already sent
        already = await session.execute(
            select(ScheduledReminder).where(and_(
                ScheduledReminder.user_id == user.id,
                ScheduledReminder.reminder_type == reminder_key,
                ScheduledReminder.sent_at >= today_start,
            ))
        )
        if already.scalar_one_or_none():
            continue

        followup = _build_followup(event)
        if not followup:
            continue

        question, yes_text, yes_cb, no_text, no_cb = followup

        # Append event_id to callbacks so handlers know which event triggered
        yes_cb_full = f"{yes_cb}_{event.id}"
        no_cb_full = f"{no_cb}_{event.id}"

        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton(yes_text, callback_data=yes_cb_full),
            InlineKeyboardButton(no_text, callback_data=no_cb_full),
        ]])

        msg = f"📅 *{event.title}* ist gerade vorbei.\n\n{question}"

        try:
            await bot.send_message(
                chat_id=user.telegram_id,
                text=msg,
                parse_mode="Markdown",
                reply_markup=keyboard,
            )

            reminder = ScheduledReminder(
                user_id=user.id,
                reminder_type=reminder_key,
                message=msg[:500],
                scheduled_for=datetime.utcnow(),
                status="sent",
                sent_at=datetime.utcnow(),
                auto_generated=True,
            )
            session.add(reminder)
            await session.flush()
            logger.info("Post-event followup sent to user %s for event %s", user.id, event.id)

        except Exception:
            logger.exception("Failed to send post-event followup for event %s", event.id)
