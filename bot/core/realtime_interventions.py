"""Real-time context-aware intervention engine.

Checks various health, nutrition, movement, and scheduling signals
and produces proactive nudges (in German) when thresholds are met.
"""

import logging
from collections import defaultdict
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import CalendarEvent, Log, NutritionEntry, NutrientTarget

logger = logging.getLogger(__name__)

TZ = ZoneInfo("Europe/Berlin")

# Module-level cooldown store: (user_id, intervention_type) -> last_sent datetime
_cooldowns: dict[tuple[int, str], datetime] = {}

# Default cooldown period per intervention type
DEFAULT_COOLDOWN = timedelta(hours=2)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now() -> datetime:
    """Current time in Europe/Berlin."""
    return datetime.now(TZ)


def _today_start() -> datetime:
    """Midnight today in Europe/Berlin (tz-aware)."""
    return datetime.combine(date.today(), datetime.min.time()).replace(tzinfo=TZ)


def _is_on_cooldown(user_id: int, intervention_type: str) -> bool:
    """Return True if this intervention was sent within the cooldown window."""
    key = (user_id, intervention_type)
    last = _cooldowns.get(key)
    if last is None:
        return False
    return (_now() - last) < DEFAULT_COOLDOWN


def _record_cooldown(user_id: int, intervention_type: str) -> None:
    """Record that an intervention was just sent."""
    _cooldowns[(user_id, intervention_type)] = _now()


def _make_naive(dt: datetime) -> datetime:
    """Strip tzinfo so we can compare with naive DB datetimes."""
    return dt.replace(tzinfo=None)


# ---------------------------------------------------------------------------
# 1. Hydration
# ---------------------------------------------------------------------------

async def check_hydration_intervention(
    session: AsyncSession, user_id: int
) -> dict | None:
    """Check if the user needs a water reminder.

    Triggers when:
    - Last water log was >3 hours ago
    - Current hour is between 08:00 and 22:00
    - Daily total < 2.5 L
    Also checks proportional on-track status.
    """
    now = _now()
    if not (8 <= now.hour < 22):
        return None

    today_start = _make_naive(_today_start())

    # Fetch today's water logs
    result = await session.execute(
        select(Log)
        .where(
            and_(
                Log.user_id == user_id,
                Log.log_type == "water",
                Log.logged_at >= today_start,
            )
        )
        .order_by(Log.logged_at.desc())
    )
    water_logs = result.scalars().all()

    # Calculate total litres consumed today
    total_liters = 0.0
    for log in water_logs:
        data = log.data or {}
        # Support amount in ml or liters
        amount = data.get("amount", 0)
        unit = data.get("unit", "ml")
        if unit == "l":
            total_liters += float(amount)
        else:
            total_liters += float(amount) / 1000.0

    target_liters = 2.5

    if total_liters >= target_liters:
        return None

    # Check last water log time
    last_log_time: datetime | None = None
    if water_logs:
        last_log_time = water_logs[0].logged_at
        if last_log_time.tzinfo is None:
            last_log_time = last_log_time.replace(tzinfo=TZ)

    hours_since_last = None
    if last_log_time:
        hours_since_last = (now - last_log_time).total_seconds() / 3600.0
        if hours_since_last < 3.0:
            return None
    else:
        # No water logged at all today — always intervene after 08:00
        hours_since_last = None

    # Proportional check: what fraction of the day (08-22) has passed?
    day_start_hour = 8
    day_end_hour = 22
    elapsed_hours = now.hour + now.minute / 60.0 - day_start_hour
    total_day_hours = day_end_hour - day_start_hour
    expected_fraction = max(0.0, min(1.0, elapsed_hours / total_day_hours))
    expected_liters = target_liters * expected_fraction
    gap_liters = round(max(0.0, expected_liters - total_liters), 2)

    # Determine urgency
    if total_liters == 0 and now.hour >= 12:
        urgency = "high"
    elif gap_liters > 1.0:
        urgency = "high"
    elif gap_liters > 0.5:
        urgency = "medium"
    else:
        urgency = "low"

    if hours_since_last is not None:
        time_hint = f"Dein letztes Wasser-Log war vor {int(hours_since_last)} Stunden."
    else:
        time_hint = "Du hast heute noch kein Wasser geloggt."

    remaining = round(target_liters - total_liters, 2)
    message = (
        f"\U0001F4A7 Hydration-Check: {time_hint} "
        f"Bisher {total_liters:.1f} L von {target_liters:.1f} L — "
        f"noch {remaining:.1f} L übrig. Trink jetzt ein Glas Wasser!"
    )

    return {
        "type": "hydration",
        "urgency": urgency,
        "message": message,
        "current_liters": round(total_liters, 2),
        "target_liters": target_liters,
        "gap_liters": gap_liters,
    }


# ---------------------------------------------------------------------------
# 2. Movement
# ---------------------------------------------------------------------------

async def check_movement_intervention(
    session: AsyncSession, user_id: int
) -> dict | None:
    """Suggest movement if no workout/steps logged and it's past 15:00.

    Skips the nudge if a training calendar event is scheduled for today.
    """
    now = _now()
    if now.hour < 15:
        return None

    today_start = _make_naive(_today_start())
    today_end = _make_naive(_today_start() + timedelta(days=1))

    # Check for workout or steps logs today
    result = await session.execute(
        select(func.count())
        .select_from(Log)
        .where(
            and_(
                Log.user_id == user_id,
                Log.log_type.in_(["workout", "steps"]),
                Log.logged_at >= today_start,
            )
        )
    )
    movement_count = result.scalar_one()

    if movement_count > 0:
        return None

    # Check if there's a training event scheduled today (don't nudge if so)
    result = await session.execute(
        select(func.count())
        .select_from(CalendarEvent)
        .where(
            and_(
                CalendarEvent.user_id == user_id,
                CalendarEvent.event_type == "training",
                CalendarEvent.start_time >= today_start,
                CalendarEvent.start_time < today_end,
            )
        )
    )
    training_events = result.scalar_one()

    if training_events > 0:
        return None

    # Determine urgency based on time
    if now.hour >= 20:
        urgency = "high"
        suggestion = "Ein kurzer 15-Minuten-Spaziergang reicht noch — besser als nichts!"
    elif now.hour >= 18:
        urgency = "medium"
        suggestion = "Wie wäre es mit einem Abendspaziergang oder einer kurzen Bodyweight-Session?"
    else:
        urgency = "low"
        suggestion = "Noch genug Zeit für ein Workout oder einen Spaziergang. Beweg dich!"

    message = (
        f"\U0001F3C3 Bewegungs-Erinnerung: Heute noch keine Bewegung geloggt. "
        f"{suggestion}"
    )

    return {
        "type": "movement",
        "urgency": urgency,
        "message": message,
        "suggestion": suggestion,
    }


# ---------------------------------------------------------------------------
# 3. Nutrition Timing
# ---------------------------------------------------------------------------

async def check_nutrition_timing_intervention(
    session: AsyncSession, user_id: int
) -> dict | None:
    """Check if meals are overdue based on typical meal times.

    Meal windows:
    - Frühstück: expected by 10:00
    - Mittagessen: expected by 14:00
    - Abendessen: expected by 20:00

    Also checks protein target progress.
    """
    now = _now()
    today_start = _make_naive(_today_start())

    # Fetch today's food logs
    result = await session.execute(
        select(Log)
        .where(
            and_(
                Log.user_id == user_id,
                Log.log_type == "food",
                Log.logged_at >= today_start,
            )
        )
        .order_by(Log.logged_at.asc())
    )
    food_logs = result.scalars().all()

    food_count = len(food_logs)

    # Determine which meal is missing
    missing_meal: str | None = None
    if now.hour >= 20 and food_count < 3:
        missing_meal = "Abendessen"
        urgency = "high"
    elif now.hour >= 14 and food_count < 2:
        missing_meal = "Mittagessen"
        urgency = "medium"
    elif now.hour >= 10 and food_count < 1:
        missing_meal = "Frühstück"
        urgency = "low"

    if missing_meal is None:
        return None

    # Check protein target from NutrientTarget
    protein_hint = ""
    try:
        target_result = await session.execute(
            select(NutrientTarget)
            .where(
                and_(
                    NutrientTarget.user_id == user_id,
                    NutrientTarget.nutrient == "protein_g",
                )
            )
        )
        protein_target = target_result.scalar_one_or_none()

        if protein_target and protein_target.target_min:
            # Sum today's protein
            entry_result = await session.execute(
                select(func.coalesce(func.sum(NutritionEntry.protein_g), 0.0))
                .where(
                    and_(
                        NutritionEntry.user_id == user_id,
                        NutritionEntry.date == date.today(),
                    )
                )
            )
            protein_today = float(entry_result.scalar_one())
            protein_min = float(protein_target.target_min)

            if protein_today < protein_min * 0.5 and now.hour >= 14:
                protein_hint = (
                    f" Protein bisher nur {protein_today:.0f}g von "
                    f"{protein_min:.0f}g — achte auf proteinreiche Lebensmittel!"
                )
    except Exception:
        # NutritionEntry / NutrientTarget tables may not exist yet
        logger.debug("Could not check protein target — tables may not exist yet")

    message = (
        f"\U0001F37D Ernährungs-Erinnerung: {missing_meal} noch nicht geloggt. "
        f"Bitte logge deine Mahlzeit, damit dein Tracking vollständig bleibt.{protein_hint}"
    )

    return {
        "type": "nutrition_timing",
        "urgency": urgency,
        "message": message,
        "missing_meal": missing_meal,
    }


# ---------------------------------------------------------------------------
# 4. Pre-Event
# ---------------------------------------------------------------------------

async def check_pre_event_intervention(
    session: AsyncSession, user_id: int
) -> dict | None:
    """Return a preparation reminder for events starting in the next 30 min."""
    now = _now()
    window_start = _make_naive(now)
    window_end = _make_naive(now + timedelta(minutes=30))

    result = await session.execute(
        select(CalendarEvent)
        .where(
            and_(
                CalendarEvent.user_id == user_id,
                CalendarEvent.start_time >= window_start,
                CalendarEvent.start_time <= window_end,
            )
        )
        .order_by(CalendarEvent.start_time.asc())
    )
    events = result.scalars().all()

    if not events:
        return None

    event = events[0]
    event_start = event.start_time
    if event_start.tzinfo is None:
        event_start = event_start.replace(tzinfo=TZ)
    minutes_until = int((event_start - now).total_seconds() / 60)
    minutes_until = max(0, minutes_until)

    # Build preparation tips based on event type
    tips: list[str] = []
    event_type = (event.event_type or "").lower()
    title = event.title or "Termin"

    if event_type == "training":
        tips.append("Sportkleidung bereit?")
        tips.append("Trinke vorab 500ml Wasser.")
    elif event_type == "meeting":
        tips.append("Unterlagen und Notizen vorbereitet?")
        tips.append("Trink vorher noch ein Glas Wasser.")
    elif event_type == "deadline":
        tips.append("Letzte Checks erledigt?")
    else:
        tips.append("Alles vorbereitet?")

    tips_text = " ".join(tips)

    message = (
        f"\U0001F4C5 {title} in {minutes_until} Min. — {tips_text}"
    )

    return {
        "type": "pre_event",
        "urgency": "medium" if minutes_until > 15 else "high",
        "message": message,
        "event_title": title,
        "event_type": event_type,
        "minutes_until": minutes_until,
    }


# ---------------------------------------------------------------------------
# 5. Bedtime
# ---------------------------------------------------------------------------

async def check_bedtime_intervention(
    session: AsyncSession, user_id: int
) -> dict | None:
    """Send a wind-down reminder based on sleep goal and wake time.

    Assumes wake time 06:30 and sleep goal 7-8h → target bedtime ~22:30-23:00.
    Warns if caffeine was consumed in the last 6 hours.
    """
    now = _now()

    # Default target bedtime range
    target_bedtime_hour = 22
    target_bedtime_minute = 30
    target_bedtime = now.replace(
        hour=target_bedtime_hour, minute=target_bedtime_minute, second=0, microsecond=0,
    )

    # Only trigger within 30 min before target bedtime
    minutes_to_bedtime = (target_bedtime - now).total_seconds() / 60.0
    if minutes_to_bedtime < 0 or minutes_to_bedtime > 30:
        return None

    # Check for caffeine in the last 6 hours
    caffeine_warning = ""
    try:
        six_hours_ago = _make_naive(now - timedelta(hours=6))
        caffeine_result = await session.execute(
            select(func.coalesce(func.sum(NutritionEntry.caffeine_mg), 0.0))
            .where(
                and_(
                    NutritionEntry.user_id == user_id,
                    NutritionEntry.date == date.today(),
                    NutritionEntry.created_at >= six_hours_ago,
                )
            )
        )
        recent_caffeine = float(caffeine_result.scalar_one())
        if recent_caffeine > 0:
            caffeine_warning = (
                f" \u26A0\uFE0F Achtung: Du hattest in den letzten 6 Stunden "
                f"{recent_caffeine:.0f}mg Koffein — das kann deinen Schlaf beeinträchtigen."
            )
    except Exception:
        logger.debug("Could not check caffeine — NutritionEntry table may not exist yet")

    message = (
        f"\U0001F319 Schlafenszeit naht! In {int(minutes_to_bedtime)} Min. ist deine "
        f"Ziel-Schlafenszeit ({target_bedtime_hour}:{target_bedtime_minute:02d}). "
        f"Bildschirmzeit reduzieren, Licht dimmen, zur Ruhe kommen.{caffeine_warning}"
    )

    return {
        "type": "bedtime",
        "urgency": "medium" if minutes_to_bedtime > 15 else "high",
        "message": message,
        "target_bedtime": f"{target_bedtime_hour}:{target_bedtime_minute:02d}",
        "minutes_until": int(minutes_to_bedtime),
    }


# ---------------------------------------------------------------------------
# 6. Nutrient Real-time Alert
# ---------------------------------------------------------------------------

async def check_nutrient_realtime_alert(
    session: AsyncSession, user_id: int
) -> dict | None:
    """Warn if any tracked nutrient is approaching (>80%) its max threshold."""
    try:
        # Fetch user's nutrient targets that have a max
        target_result = await session.execute(
            select(NutrientTarget)
            .where(
                and_(
                    NutrientTarget.user_id == user_id,
                    NutrientTarget.target_max.isnot(None),
                )
            )
        )
        targets = target_result.scalars().all()

        if not targets:
            return None

        # Fetch today's nutrition totals
        entry_result = await session.execute(
            select(
                func.coalesce(func.sum(NutritionEntry.calories), 0.0).label("calories"),
                func.coalesce(func.sum(NutritionEntry.protein_g), 0.0).label("protein_g"),
                func.coalesce(func.sum(NutritionEntry.sodium_mg), 0.0).label("sodium_mg"),
                func.coalesce(func.sum(NutritionEntry.caffeine_mg), 0.0).label("caffeine_mg"),
            )
            .where(
                and_(
                    NutritionEntry.user_id == user_id,
                    NutritionEntry.date == date.today(),
                )
            )
        )
        totals = entry_result.one()

        # Map nutrient names to their summed values
        nutrient_values = {
            "calories": float(totals.calories),
            "protein_g": float(totals.protein_g),
            "sodium_mg": float(totals.sodium_mg),
            "caffeine_mg": float(totals.caffeine_mg),
        }

        # Human-readable German labels
        nutrient_labels = {
            "calories": "Kalorien",
            "protein_g": "Protein",
            "sodium_mg": "Natrium",
            "caffeine_mg": "Koffein",
        }

        warnings: list[str] = []
        for target in targets:
            nutrient = target.nutrient
            max_val = float(target.target_max)
            current = nutrient_values.get(nutrient, 0.0)

            if max_val > 0 and current >= max_val * 0.8:
                pct = int((current / max_val) * 100)
                label = nutrient_labels.get(nutrient, nutrient)
                warnings.append(f"{label}: {current:.0f}/{max_val:.0f} ({pct}%)")

        if not warnings:
            return None

        urgency = "high" if any(
            nutrient_values.get(t.nutrient, 0) >= float(t.target_max) * 0.95
            for t in targets
            if t.target_max
        ) else "medium"

        warning_text = ", ".join(warnings)
        message = (
            f"\u26A0\uFE0F Nährstoff-Warnung: Du näherst dich dem Tageslimit! "
            f"{warning_text}. Achte auf deine verbleibende Zufuhr."
        )

        return {
            "type": "nutrient_alert",
            "urgency": urgency,
            "message": message,
            "warnings": warnings,
        }
    except Exception:
        logger.debug("Could not check nutrient alerts — tables may not exist yet")
        return None


# ---------------------------------------------------------------------------
# 7. Run All Interventions
# ---------------------------------------------------------------------------

async def run_all_interventions(
    session: AsyncSession, user_id: int
) -> list[dict]:
    """Execute every intervention check, respecting per-type cooldowns.

    Returns a list of triggered interventions (those not on cooldown).
    """
    checks = [
        ("hydration", check_hydration_intervention),
        ("movement", check_movement_intervention),
        ("nutrition_timing", check_nutrition_timing_intervention),
        ("pre_event", check_pre_event_intervention),
        ("bedtime", check_bedtime_intervention),
        ("nutrient_alert", check_nutrient_realtime_alert),
    ]

    triggered: list[dict] = []

    for intervention_type, check_fn in checks:
        if _is_on_cooldown(user_id, intervention_type):
            continue
        try:
            result = await check_fn(session, user_id)
            if result is not None:
                _record_cooldown(user_id, intervention_type)
                triggered.append(result)
        except Exception:
            logger.exception(
                "Error running intervention check '%s' for user %d",
                intervention_type,
                user_id,
            )

    return triggered


# ---------------------------------------------------------------------------
# 8. Format for Telegram
# ---------------------------------------------------------------------------

def format_intervention_message(intervention: dict) -> str:
    """Format an intervention dict into a user-friendly Telegram message (German).

    Uses the pre-built 'message' field and adds urgency decoration.
    """
    urgency = intervention.get("urgency", "low")
    message = intervention.get("message", "")

    # Add urgency prefix
    if urgency == "high":
        prefix = "\U0001F534 WICHTIG"
    elif urgency == "medium":
        prefix = "\U0001F7E1 Hinweis"
    else:
        prefix = "\U0001F7E2 Tipp"

    return f"{prefix}\n{message}"
