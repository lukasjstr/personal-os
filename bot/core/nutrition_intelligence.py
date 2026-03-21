"""Nutrition Intelligence engine — GPT-powered nutrient estimation, tracking, alerts, and trend analysis."""

import json
import logging
from datetime import date, datetime, timedelta
from typing import Any, Optional

from openai import AsyncOpenAI
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import settings
from bot.database.models import DailyContext, Log, NutrientTarget, NutritionEntry

logger = logging.getLogger(__name__)

_openai = AsyncOpenAI(api_key=settings.openai_api_key)

# ---------------------------------------------------------------------------
# Macro/micro nutrient fields stored as dedicated columns
# ---------------------------------------------------------------------------
NUTRIENT_COLUMNS: dict[str, str] = {
    "calories": "calories",
    "protein_g": "protein_g",
    "carbs_g": "carbs_g",
    "fat_g": "fat_g",
    "fiber_g": "fiber_g",
    "sugar_g": "sugar_g",
    "sodium_mg": "sodium_mg",
    "potassium_mg": "potassium_mg",
    "caffeine_mg": "caffeine_mg",
    "water_ml": "water_ml",
}

# ---------------------------------------------------------------------------
# Default nutrient targets (WHO / DGE recommendations)
# ---------------------------------------------------------------------------
DEFAULT_TARGETS: list[dict[str, Any]] = [
    {"nutrient": "calories", "target_min": 2000, "target_max": 2500, "unit": "kcal"},
    {"nutrient": "protein_g", "target_min": 50, "target_max": 200, "unit": "g"},
    {"nutrient": "carbs_g", "target_min": 50, "target_max": 300, "unit": "g"},
    {"nutrient": "fat_g", "target_min": 40, "target_max": 100, "unit": "g"},
    {"nutrient": "fiber_g", "target_min": 25, "target_max": 40, "unit": "g"},
    {"nutrient": "sugar_g", "target_min": 0, "target_max": 50, "unit": "g"},
    {"nutrient": "sodium_mg", "target_min": 0, "target_max": 2300, "unit": "mg"},
    {"nutrient": "potassium_mg", "target_min": 3500, "target_max": 5000, "unit": "mg"},
    {"nutrient": "caffeine_mg", "target_min": 0, "target_max": 400, "unit": "mg"},
    {"nutrient": "water_ml", "target_min": 2500, "target_max": 4000, "unit": "ml"},
]

# Human-readable German labels
_GERMAN_LABELS: dict[str, str] = {
    "calories": "Kalorien",
    "protein_g": "Protein",
    "carbs_g": "Kohlenhydrate",
    "fat_g": "Fett",
    "fiber_g": "Ballaststoffe",
    "sugar_g": "Zucker",
    "sodium_mg": "Natrium",
    "potassium_mg": "Kalium",
    "caffeine_mg": "Koffein",
    "water_ml": "Wasser",
}


def _label(nutrient: str) -> str:
    return _GERMAN_LABELS.get(nutrient, nutrient)


# ===================================================================
# 1. GPT-powered nutrient estimation
# ===================================================================

async def estimate_nutrients(description: str) -> dict[str, Any]:
    """Use GPT-4o to estimate macro- and micronutrients from a food description.

    Returns a dict with at least: calories, protein_g, carbs_g, fat_g, fiber_g,
    sugar_g, sodium_mg, potassium_mg, caffeine_mg, water_ml.  Additional
    detected nutrients are included under their own keys.
    """
    prompt = (
        "Du bist ein Ernährungswissenschaftler. Schätze die Nährstoffe für die "
        "folgende Mahlzeit / das folgende Lebensmittel so genau wie möglich.\n\n"
        f"Beschreibung: {description}\n\n"
        "Antworte ausschließlich als JSON-Objekt mit mindestens diesen Feldern:\n"
        "  calories (kcal), protein_g, carbs_g, fat_g, fiber_g, sugar_g,\n"
        "  sodium_mg, potassium_mg, caffeine_mg, water_ml\n\n"
        "Falls du zusätzliche relevante Mikronährstoffe erkennen kannst "
        "(z.B. vitamin_c_mg, iron_mg, calcium_mg, magnesium_mg, zinc_mg, "
        "vitamin_b12_mcg, omega3_g), füge sie als weitere Felder hinzu.\n"
        "Alle Werte als Zahlen (keine Strings). Schätze realistisch anhand "
        "typischer Portionsgrößen."
    )

    try:
        response = await _openai.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.2,
            max_tokens=600,
        )
        content = response.choices[0].message.content
        data: dict[str, Any] = json.loads(content)  # type: ignore[arg-type]

        # Ensure all core fields are present with fallback 0
        for key in NUTRIENT_COLUMNS:
            data.setdefault(key, 0)

        logger.info("Nährstoffschätzung für '%s': %s kcal", description, data.get("calories"))
        return data

    except Exception:
        logger.exception("Fehler bei GPT-Nährstoffschätzung für '%s'", description)
        # Return zeroed fallback so callers can still proceed
        return {k: 0 for k in NUTRIENT_COLUMNS}


# ===================================================================
# 2. Store a NutritionEntry
# ===================================================================

async def log_nutrition(
    session: AsyncSession,
    user_id: int,
    log_id: int,
    food_description: str,
    meal_type: str,
    estimated_nutrients: dict[str, Any],
) -> NutritionEntry:
    """Persist a NutritionEntry in the database and return it."""
    # Separate core columns from additional nutrients
    additional: dict[str, Any] = {}
    core_values: dict[str, Any] = {}

    for key, value in estimated_nutrients.items():
        if key in NUTRIENT_COLUMNS:
            core_values[key] = value
        else:
            additional[key] = value

    entry = NutritionEntry(
        user_id=user_id,
        log_id=log_id,
        date=date.today(),
        food_description=food_description,
        meal_type=meal_type,
        additional_nutrients=additional if additional else None,
        **core_values,
    )
    session.add(entry)
    await session.flush()
    logger.info(
        "NutritionEntry %s erstellt: user=%s, meal=%s, %s kcal",
        entry.id, user_id, meal_type, core_values.get("calories", 0),
    )
    return entry


# ===================================================================
# 3. Daily totals
# ===================================================================

async def get_daily_totals(
    session: AsyncSession,
    user_id: int,
    target_date: date,
) -> dict[str, float]:
    """Aggregate all NutritionEntry rows for *target_date* and return totals."""
    sums = {col: func.coalesce(func.sum(getattr(NutritionEntry, col)), 0) for col in NUTRIENT_COLUMNS}

    stmt = (
        select(*sums.values())
        .where(and_(
            NutritionEntry.user_id == user_id,
            NutritionEntry.date == target_date,
        ))
    )
    row = (await session.execute(stmt)).one()

    totals: dict[str, float] = {}
    for i, col_name in enumerate(NUTRIENT_COLUMNS):
        totals[col_name] = float(row[i] or 0)

    # Aggregate JSONB additional_nutrients
    entries_stmt = (
        select(NutritionEntry.additional_nutrients)
        .where(and_(
            NutritionEntry.user_id == user_id,
            NutritionEntry.date == target_date,
            NutritionEntry.additional_nutrients.is_not(None),
        ))
    )
    rows = (await session.execute(entries_stmt)).scalars().all()
    for extra in rows:
        if not isinstance(extra, dict):
            continue
        for k, v in extra.items():
            if isinstance(v, (int, float)):
                totals[k] = totals.get(k, 0) + v

    return totals


# ===================================================================
# 4. Nutrient alerts
# ===================================================================

async def check_nutrient_alerts(
    session: AsyncSession,
    user_id: int,
    target_date: date,
) -> list[dict[str, Any]]:
    """Compare today's totals against targets and historical data.

    Returns a list of alert dicts.
    """
    totals = await get_daily_totals(session, user_id, target_date)
    alerts: list[dict[str, Any]] = []

    # --- Target-based alerts ---
    targets_stmt = select(NutrientTarget).where(and_(
        NutrientTarget.user_id == user_id,
        NutrientTarget.is_active == True,  # noqa: E712
    ))
    targets = list((await session.execute(targets_stmt)).scalars().all())

    target_map: dict[str, NutrientTarget] = {t.nutrient: t for t in targets}

    for nutrient, current in totals.items():
        target = target_map.get(nutrient)
        if not target:
            continue

        label = _label(nutrient)

        if target.target_max is not None and current > target.target_max:
            severity = "critical" if current > target.target_max * 1.2 else "warning"
            alerts.append({
                "nutrient": nutrient,
                "current_value": current,
                "threshold": target.target_max,
                "alert_type": "exceeded_max",
                "message": f"{label}: {current:.0f} überschreitet das Maximum von {target.target_max:.0f} {target.unit}",
                "severity": severity,
                "explanation": f"Dein {label}-Wert liegt über dem empfohlenen Tagesmaximum.",
            })

        if target.target_min is not None and current < target.target_min:
            severity = "critical" if current < target.target_min * 0.5 else "warning"
            alerts.append({
                "nutrient": nutrient,
                "current_value": current,
                "threshold": target.target_min,
                "alert_type": "below_min",
                "message": f"{label}: {current:.0f} liegt unter dem Minimum von {target.target_min:.0f} {target.unit}",
                "severity": severity,
                "explanation": f"Dein {label}-Wert liegt unter dem empfohlenen Tagesminimum.",
            })

    # --- Historical anomaly detection (last 30 days) ---
    history_start = target_date - timedelta(days=30)
    for col_name in NUTRIENT_COLUMNS:
        col = getattr(NutritionEntry, col_name)
        stats_stmt = (
            select(
                func.avg(func.coalesce(col, 0)),
                func.stddev(func.coalesce(col, 0)),
                func.max(func.coalesce(col, 0)),
            )
            .where(and_(
                NutritionEntry.user_id == user_id,
                NutritionEntry.date >= history_start,
                NutritionEntry.date < target_date,
            ))
            .group_by(NutritionEntry.date)
        )
        # We need daily sums first, then stats over those
        daily_sum_subq = (
            select(
                func.sum(func.coalesce(col, 0)).label("daily_total"),
            )
            .where(and_(
                NutritionEntry.user_id == user_id,
                NutritionEntry.date >= history_start,
                NutritionEntry.date < target_date,
            ))
            .group_by(NutritionEntry.date)
            .subquery()
        )
        agg_stmt = select(
            func.avg(daily_sum_subq.c.daily_total),
            func.stddev(daily_sum_subq.c.daily_total),
        )
        agg_row = (await session.execute(agg_stmt)).one()
        avg_val = float(agg_row[0]) if agg_row[0] is not None else None
        std_val = float(agg_row[1]) if agg_row[1] is not None else None

        if avg_val is None or std_val is None or std_val == 0:
            continue

        current = totals.get(col_name, 0)
        label = _label(col_name)

        if current > avg_val + 2 * std_val:
            alerts.append({
                "nutrient": col_name,
                "current_value": current,
                "threshold": round(avg_val + 2 * std_val, 1),
                "alert_type": "historical_high",
                "message": f"{label}: {current:.0f} ist deutlich über deinem 30-Tage-Durchschnitt ({avg_val:.0f})",
                "severity": "warning",
                "explanation": f"Dein heutiger {label}-Wert ist statistisch ungewöhnlich hoch (>2 Standardabweichungen).",
            })
        elif current < avg_val - 2 * std_val and current >= 0:
            alerts.append({
                "nutrient": col_name,
                "current_value": current,
                "threshold": round(avg_val - 2 * std_val, 1),
                "alert_type": "historical_low",
                "message": f"{label}: {current:.0f} ist deutlich unter deinem 30-Tage-Durchschnitt ({avg_val:.0f})",
                "severity": "warning",
                "explanation": f"Dein heutiger {label}-Wert ist statistisch ungewöhnlich niedrig (<2 Standardabweichungen).",
            })

    return alerts


# ===================================================================
# 5. Nutrition trends
# ===================================================================

async def get_nutrition_trends(
    session: AsyncSession,
    user_id: int,
    days: int = 30,
) -> dict[str, Any]:
    """Return daily averages, trends, and notable patterns for tracked nutrients."""
    start_date = date.today() - timedelta(days=days)

    # Build daily sums per nutrient
    daily_data: dict[str, list[float]] = {col: [] for col in NUTRIENT_COLUMNS}
    dates_with_data: list[date] = []

    for col_name in NUTRIENT_COLUMNS:
        col = getattr(NutritionEntry, col_name)
        stmt = (
            select(
                NutritionEntry.date,
                func.sum(func.coalesce(col, 0)).label("total"),
            )
            .where(and_(
                NutritionEntry.user_id == user_id,
                NutritionEntry.date >= start_date,
            ))
            .group_by(NutritionEntry.date)
            .order_by(NutritionEntry.date)
        )
        rows = (await session.execute(stmt)).all()
        for row in rows:
            daily_data[col_name].append(float(row.total))
            if col_name == "calories" and row.date not in dates_with_data:
                dates_with_data.append(row.date)

    result: dict[str, Any] = {
        "period_days": days,
        "days_tracked": len(dates_with_data),
        "nutrients": {},
    }

    for col_name, values in daily_data.items():
        if not values:
            continue
        avg = sum(values) / len(values)
        # Simple trend: compare first half vs second half average
        mid = len(values) // 2
        if mid > 0:
            first_half = sum(values[:mid]) / mid
            second_half = sum(values[mid:]) / len(values[mid:])
            trend_pct = ((second_half - first_half) / first_half * 100) if first_half > 0 else 0
            if trend_pct > 10:
                trend = "steigend"
            elif trend_pct < -10:
                trend = "sinkend"
            else:
                trend = "stabil"
        else:
            trend = "zu wenig Daten"
            trend_pct = 0

        result["nutrients"][col_name] = {
            "label": _label(col_name),
            "avg": round(avg, 1),
            "min": round(min(values), 1),
            "max": round(max(values), 1),
            "trend": trend,
            "trend_pct": round(trend_pct, 1),
        }

    # Notable patterns
    patterns: list[str] = []
    cal_data = result["nutrients"].get("calories", {})
    if cal_data.get("trend") == "steigend":
        patterns.append(f"Kalorienzufuhr steigt (Ø +{cal_data.get('trend_pct', 0):.0f}% in der zweiten Hälfte)")
    prot_data = result["nutrients"].get("protein_g", {})
    if prot_data.get("avg", 0) < 50:
        patterns.append("Proteinzufuhr liegt unter dem empfohlenen Minimum von 50g/Tag")
    fiber_data = result["nutrients"].get("fiber_g", {})
    if fiber_data.get("avg", 0) < 25:
        patterns.append("Ballaststoffe liegen unter der Empfehlung von 25g/Tag")
    water_data = result["nutrients"].get("water_ml", {})
    if water_data.get("avg", 0) < 2500:
        patterns.append("Wasseraufnahme liegt unter dem empfohlenen Minimum von 2500ml/Tag")

    result["patterns"] = patterns
    return result


# ===================================================================
# 6. Nutrient ↔ sleep / mood / energy correlations
# ===================================================================

async def get_nutrient_correlations(
    session: AsyncSession,
    user_id: int,
) -> list[dict[str, Any]]:
    """Cross-reference nutrition with sleep, mood, and energy data.

    Looks at the last 60 days for meaningful correlations.
    """
    start_date = date.today() - timedelta(days=60)
    correlations: list[dict[str, Any]] = []

    # Gather daily nutrition sums
    nutrition_by_date: dict[date, dict[str, float]] = {}
    for col_name in NUTRIENT_COLUMNS:
        col = getattr(NutritionEntry, col_name)
        stmt = (
            select(NutritionEntry.date, func.sum(func.coalesce(col, 0)).label("total"))
            .where(and_(
                NutritionEntry.user_id == user_id,
                NutritionEntry.date >= start_date,
            ))
            .group_by(NutritionEntry.date)
        )
        for row in (await session.execute(stmt)).all():
            nutrition_by_date.setdefault(row.date, {})[col_name] = float(row.total)

    if not nutrition_by_date:
        return []

    # Gather sleep logs
    sleep_stmt = (
        select(Log)
        .where(and_(
            Log.user_id == user_id,
            Log.log_type == "sleep",
            Log.logged_at >= datetime.combine(start_date, datetime.min.time()),
        ))
    )
    sleep_logs = list((await session.execute(sleep_stmt)).scalars().all())
    sleep_by_date: dict[date, dict[str, Any]] = {}
    for sl in sleep_logs:
        d = sl.logged_at.date()
        if isinstance(sl.data, dict):
            sleep_by_date[d] = sl.data

    # Gather energy from DailyContext
    energy_stmt = (
        select(DailyContext.date, DailyContext.energy)
        .where(and_(
            DailyContext.user_id == user_id,
            DailyContext.date >= start_date,
            DailyContext.energy.is_not(None),
        ))
    )
    energy_by_date: dict[date, int] = {}
    for row in (await session.execute(energy_stmt)).all():
        energy_by_date[row.date] = row.energy

    # Gather mood logs
    mood_stmt = (
        select(Log)
        .where(and_(
            Log.user_id == user_id,
            Log.log_type == "mood",
            Log.logged_at >= datetime.combine(start_date, datetime.min.time()),
        ))
    )
    mood_logs = list((await session.execute(mood_stmt)).scalars().all())
    mood_by_date: dict[date, Any] = {}
    for ml in mood_logs:
        d = ml.logged_at.date()
        if isinstance(ml.data, dict):
            mood_by_date[d] = ml.data

    # --- Correlation checks ---

    # High sodium → poor sleep
    high_sodium_days = [d for d, n in nutrition_by_date.items() if n.get("sodium_mg", 0) > 2300]
    low_sodium_days = [d for d, n in nutrition_by_date.items() if n.get("sodium_mg", 0) <= 1500]
    if high_sodium_days and sleep_by_date:
        high_na_sleep = _avg_sleep_quality(high_sodium_days, sleep_by_date)
        low_na_sleep = _avg_sleep_quality(low_sodium_days, sleep_by_date)
        if high_na_sleep is not None and low_na_sleep is not None and high_na_sleep < low_na_sleep:
            correlations.append({
                "nutrient": "sodium_mg",
                "correlated_with": "sleep_quality",
                "direction": "negative",
                "message": (
                    f"An Tagen mit hohem Natriumkonsum (>2300mg) war deine Schlafqualität "
                    f"im Schnitt {low_na_sleep - high_na_sleep:.1f} Punkte niedriger."
                ),
                "sample_size": len(high_sodium_days),
            })

    # Late caffeine → poor sleep
    # Check nutrition entries with caffeine logged after 14:00
    late_caffeine_stmt = (
        select(NutritionEntry.date)
        .where(and_(
            NutritionEntry.user_id == user_id,
            NutritionEntry.date >= start_date,
            NutritionEntry.caffeine_mg > 0,
            NutritionEntry.created_at >= func.cast(
                func.concat(func.cast(NutritionEntry.date, type_=func.text.__class__), " 14:00:00"),
                type_=NutritionEntry.created_at.type,
            ) if hasattr(func, 'text') else True,
        ))
        .distinct()
    )
    try:
        # Simpler approach: fetch all caffeine entries and filter in Python
        all_caffeine_stmt = (
            select(NutritionEntry)
            .where(and_(
                NutritionEntry.user_id == user_id,
                NutritionEntry.date >= start_date,
                NutritionEntry.caffeine_mg > 0,
            ))
        )
        caffeine_entries = list((await session.execute(all_caffeine_stmt)).scalars().all())
        late_caffeine_dates = set()
        early_caffeine_dates = set()
        for entry in caffeine_entries:
            if entry.created_at and entry.created_at.hour >= 14:
                late_caffeine_dates.add(entry.date)
            else:
                early_caffeine_dates.add(entry.date)

        if late_caffeine_dates and sleep_by_date:
            late_sleep = _avg_sleep_quality(list(late_caffeine_dates), sleep_by_date)
            early_sleep = _avg_sleep_quality(list(early_caffeine_dates), sleep_by_date)
            if late_sleep is not None and early_sleep is not None and late_sleep < early_sleep:
                correlations.append({
                    "nutrient": "caffeine_mg",
                    "correlated_with": "sleep_quality",
                    "direction": "negative",
                    "message": (
                        f"Koffein nach 14 Uhr korreliert mit schlechterer Schlafqualität "
                        f"(Ø {early_sleep - late_sleep:.1f} Punkte weniger)."
                    ),
                    "sample_size": len(late_caffeine_dates),
                })
    except Exception:
        logger.debug("Koffein-Schlaf-Korrelation konnte nicht berechnet werden", exc_info=True)

    # Low protein → low energy
    if energy_by_date:
        low_protein_days = [d for d, n in nutrition_by_date.items() if n.get("protein_g", 0) < 50]
        high_protein_days = [d for d, n in nutrition_by_date.items() if n.get("protein_g", 0) >= 80]
        low_prot_energy = _avg_value_on_dates(low_protein_days, energy_by_date)
        high_prot_energy = _avg_value_on_dates(high_protein_days, energy_by_date)
        if low_prot_energy is not None and high_prot_energy is not None and low_prot_energy < high_prot_energy:
            correlations.append({
                "nutrient": "protein_g",
                "correlated_with": "energy",
                "direction": "positive",
                "message": (
                    f"An Tagen mit niedrigem Protein (<50g) war dein Energielevel "
                    f"im Schnitt {high_prot_energy - low_prot_energy:.1f} Punkte niedriger."
                ),
                "sample_size": len(low_protein_days),
            })

    # High sugar → mood dip (next day)
    if mood_by_date:
        high_sugar_days = [d for d, n in nutrition_by_date.items() if n.get("sugar_g", 0) > 60]
        normal_sugar_days = [d for d, n in nutrition_by_date.items() if n.get("sugar_g", 0) <= 30]
        high_sugar_next = [d + timedelta(days=1) for d in high_sugar_days]
        normal_sugar_next = [d + timedelta(days=1) for d in normal_sugar_days]
        high_mood = _avg_mood(high_sugar_next, mood_by_date)
        normal_mood = _avg_mood(normal_sugar_next, mood_by_date)
        if high_mood is not None and normal_mood is not None and high_mood < normal_mood:
            correlations.append({
                "nutrient": "sugar_g",
                "correlated_with": "mood",
                "direction": "negative",
                "message": (
                    f"Nach Tagen mit hohem Zuckerkonsum (>60g) war deine Stimmung am Folgetag "
                    f"im Schnitt {normal_mood - high_mood:.1f} Punkte niedriger."
                ),
                "sample_size": len(high_sugar_days),
            })

    return correlations


def _avg_sleep_quality(dates: list[date], sleep_data: dict[date, dict]) -> Optional[float]:
    """Compute average sleep quality across the given dates."""
    values = []
    for d in dates:
        s = sleep_data.get(d)
        if s and isinstance(s, dict):
            q = s.get("quality") or s.get("sleep_quality") or s.get("rating")
            if isinstance(q, (int, float)):
                values.append(q)
    return sum(values) / len(values) if values else None


def _avg_value_on_dates(dates: list[date], data: dict[date, Any]) -> Optional[float]:
    """Compute average numeric value on given dates."""
    values = [data[d] for d in dates if d in data and isinstance(data[d], (int, float))]
    return sum(values) / len(values) if values else None


def _avg_mood(dates: list[date], mood_data: dict[date, dict]) -> Optional[float]:
    """Compute average mood score across the given dates."""
    values = []
    for d in dates:
        m = mood_data.get(d)
        if m and isinstance(m, dict):
            score = m.get("score") or m.get("mood") or m.get("rating")
            if isinstance(score, (int, float)):
                values.append(score)
    return sum(values) / len(values) if values else None


# ===================================================================
# 7. Historical rank
# ===================================================================

async def get_historical_rank(
    session: AsyncSession,
    user_id: int,
    nutrient: str,
    value: float,
) -> dict[str, Any]:
    """Return where *value* ranks among all historical daily totals for *nutrient*."""
    if nutrient not in NUTRIENT_COLUMNS:
        return {"rank": 0, "total_days": 0, "percentile": 0, "message": "Unbekannter Nährstoff"}

    col = getattr(NutritionEntry, nutrient)
    daily_totals_subq = (
        select(func.sum(func.coalesce(col, 0)).label("daily_total"))
        .where(NutritionEntry.user_id == user_id)
        .group_by(NutritionEntry.date)
        .subquery()
    )

    # Count total days and days with a higher total
    total_stmt = select(func.count()).select_from(daily_totals_subq)
    higher_stmt = (
        select(func.count())
        .select_from(daily_totals_subq)
        .where(daily_totals_subq.c.daily_total > value)
    )

    total_days = (await session.execute(total_stmt)).scalar() or 0
    days_higher = (await session.execute(higher_stmt)).scalar() or 0

    rank = days_higher + 1
    percentile = round(((total_days - rank + 1) / total_days) * 100, 1) if total_days > 0 else 0
    label = _label(nutrient)

    if rank == 1:
        message = f"Höchster {label}-Wert seit Aufzeichnungsbeginn!"
    elif rank == 2:
        message = f"Zweithöchster {label}-Wert seit Aufzeichnungsbeginn"
    elif rank <= 3:
        message = f"Dritthöchster {label}-Wert seit Aufzeichnungsbeginn"
    elif percentile >= 90:
        message = f"Top 10% — überdurchschnittlich hoher {label}-Wert"
    elif percentile <= 10:
        message = f"Unter den niedrigsten 10% — sehr niedriger {label}-Wert"
    else:
        message = f"{label}: Rang {rank} von {total_days} Tagen ({percentile:.0f}. Perzentil)"

    return {
        "rank": rank,
        "total_days": total_days,
        "percentile": percentile,
        "message": message,
    }


# ===================================================================
# 8. Default targets
# ===================================================================

async def set_default_targets(
    session: AsyncSession,
    user_id: int,
) -> list[NutrientTarget]:
    """Create sensible default nutrient targets based on WHO/DGE recommendations.

    Existing active targets for the same nutrient are deactivated first.
    """
    created: list[NutrientTarget] = []

    for spec in DEFAULT_TARGETS:
        # Deactivate any existing target for this nutrient
        existing_stmt = select(NutrientTarget).where(and_(
            NutrientTarget.user_id == user_id,
            NutrientTarget.nutrient == spec["nutrient"],
            NutrientTarget.is_active == True,  # noqa: E712
        ))
        existing = (await session.execute(existing_stmt)).scalars().all()
        for ex in existing:
            ex.is_active = False

        target = NutrientTarget(
            user_id=user_id,
            nutrient=spec["nutrient"],
            target_min=spec["target_min"],
            target_max=spec["target_max"],
            unit=spec["unit"],
            is_active=True,
        )
        session.add(target)
        created.append(target)

    await session.flush()
    logger.info("Standard-Nährstoffziele für user %s erstellt (%d Ziele)", user_id, len(created))
    return created
