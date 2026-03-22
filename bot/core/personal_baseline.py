"""Personal Baseline Engine — rolling averages and anomaly detection relative to personal history.

For each tracked metric (sleep, sodium, calories, mood, water, steps, HRV, etc.) this engine:
  1. Maintains a 30-day and 90-day rolling mean + std
  2. Computes anomaly scores: how many std deviations above/below mean
  3. Returns human-readable context: "Höchster Wert seit 14 Tagen"
  4. Caches results in personal_baselines table (updated daily)

Usage:
    score = await get_anomaly_score(session, user_id, "sodium_mg", today_value=6200)
    # Returns: AnomalyResult(z_score=2.3, percentile_rank=97, label="Höchster Wert seit 22 Tagen")
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import FoodEntry, Log, PersonalBaseline

logger = logging.getLogger(__name__)

# Metric definitions: how to extract daily values from the database
METRIC_SOURCES = {
    "sleep_hours":  ("log", "sleep", "hours"),
    "sleep_quality": ("log", "sleep", "quality"),
    "mood":         ("log", "mood", "score"),
    "water_liters": ("log", "water", "amount"),  # summed per day
    "steps":        ("log", "steps", "count"),
    "hrv":          ("log", "hrv", "score"),
    "sodium_mg":    ("food_entry", None, "sodium_mg"),  # summed per day
    "calories":     ("food_entry", None, "calories"),   # summed per day
    "protein_g":    ("food_entry", None, "protein_g"),  # summed per day
    "carbs_g":      ("food_entry", None, "carbs_g"),    # summed per day
    "fat_g":        ("food_entry", None, "fat_g"),      # summed per day
}


@dataclass
class AnomalyResult:
    metric_key: str
    current_value: float
    mean_30d: Optional[float]
    std_30d: Optional[float]
    z_score: Optional[float]          # standard deviations from mean
    days_tracked: int
    rank_position: Optional[int]      # rank among all tracked values (1=highest)
    rank_total: int                   # total days with data
    is_anomaly: bool                  # |z_score| > 1.5
    direction: str                    # "high", "low", "normal"
    label: str                        # human-readable: "Höchster Wert seit 14 Tagen"


async def get_anomaly_score(
    session: AsyncSession,
    user_id: int,
    metric_key: str,
    current_value: float,
    days_back: int = 90,
) -> AnomalyResult:
    """Compute anomaly score for a current value relative to personal history."""
    history = await _get_metric_history(session, user_id, metric_key, days_back)

    if len(history) < 3:
        return AnomalyResult(
            metric_key=metric_key,
            current_value=current_value,
            mean_30d=None,
            std_30d=None,
            z_score=None,
            days_tracked=len(history),
            rank_position=None,
            rank_total=len(history),
            is_anomaly=False,
            direction="normal",
            label="Nicht genug Daten für Vergleich",
        )

    # 30-day window
    recent = history[-30:] if len(history) >= 30 else history
    mean_30d = sum(recent) / len(recent)
    std_30d = math.sqrt(sum((v - mean_30d) ** 2 for v in recent) / len(recent)) if len(recent) > 1 else 0

    z_score = (current_value - mean_30d) / std_30d if std_30d > 0 else 0.0

    # Rank position: how does today compare to all historical values?
    all_values_sorted = sorted(history + [current_value], reverse=True)
    rank_position = all_values_sorted.index(current_value) + 1
    rank_total = len(all_values_sorted)

    is_anomaly = abs(z_score) > 1.5
    direction = "high" if z_score > 1.5 else "low" if z_score < -1.5 else "normal"

    label = _build_label(metric_key, current_value, rank_position, rank_total, z_score, mean_30d, history)

    return AnomalyResult(
        metric_key=metric_key,
        current_value=current_value,
        mean_30d=round(mean_30d, 1),
        std_30d=round(std_30d, 1),
        z_score=round(z_score, 2),
        days_tracked=len(history),
        rank_position=rank_position,
        rank_total=rank_total,
        is_anomaly=is_anomaly,
        direction=direction,
        label=label,
    )


async def update_baselines_for_user(session: AsyncSession, user_id: int) -> None:
    """Recompute and cache all baselines for a user. Called daily by scheduler."""
    for metric_key in METRIC_SOURCES:
        try:
            history_90 = await _get_metric_history(session, user_id, metric_key, days_back=90)
            history_30 = history_90[-30:] if len(history_90) >= 30 else history_90

            mean_30d = (sum(history_30) / len(history_30)) if history_30 else None
            std_30d = (
                math.sqrt(sum((v - mean_30d) ** 2 for v in history_30) / len(history_30))
                if len(history_30) > 1 and mean_30d is not None else None
            )
            mean_90d = (sum(history_90) / len(history_90)) if history_90 else None
            min_ever = min(history_90) if history_90 else None
            max_ever = max(history_90) if history_90 else None

            # Upsert
            existing = (await session.execute(
                select(PersonalBaseline).where(and_(
                    PersonalBaseline.user_id == user_id,
                    PersonalBaseline.metric_key == metric_key,
                ))
            )).scalar_one_or_none()

            if existing:
                existing.mean_30d = mean_30d
                existing.std_30d = std_30d
                existing.mean_90d = mean_90d
                existing.min_ever = min_ever
                existing.max_ever = max_ever
                existing.days_tracked = len(history_90)
                existing.last_updated = datetime.utcnow()
            else:
                session.add(PersonalBaseline(
                    user_id=user_id,
                    metric_key=metric_key,
                    mean_30d=mean_30d,
                    std_30d=std_30d,
                    mean_90d=mean_90d,
                    min_ever=min_ever,
                    max_ever=max_ever,
                    days_tracked=len(history_90),
                ))
        except Exception as e:
            logger.warning("Baseline update failed for %s/%s: %s", user_id, metric_key, e)

    await session.flush()


async def get_cached_baseline(
    session: AsyncSession,
    user_id: int,
    metric_key: str,
) -> Optional[PersonalBaseline]:
    """Fetch cached baseline from DB."""
    return (await session.execute(
        select(PersonalBaseline).where(and_(
            PersonalBaseline.user_id == user_id,
            PersonalBaseline.metric_key == metric_key,
        ))
    )).scalar_one_or_none()


# ── Internal helpers ─────────────────────────────────────────────────────────

async def _get_metric_history(
    session: AsyncSession,
    user_id: int,
    metric_key: str,
    days_back: int = 90,
) -> list[float]:
    """Fetch historical daily values for a metric (oldest first)."""
    if metric_key not in METRIC_SOURCES:
        return []

    source, log_type, field = METRIC_SOURCES[metric_key]
    since = datetime.combine(date.today() - timedelta(days=days_back), datetime.min.time())

    if source == "log":
        logs = (await session.execute(
            select(Log).where(and_(
                Log.user_id == user_id,
                Log.log_type == log_type,
                Log.logged_at >= since,
            )).order_by(Log.logged_at)
        )).scalars().all()

        if metric_key == "water_liters":
            # Sum per day
            daily: dict[str, float] = {}
            for log in logs:
                d = log.logged_at.strftime("%Y-%m-%d")
                val = (log.data or {}).get(field)
                if val is not None:
                    daily[d] = daily.get(d, 0) + float(val)
            return list(daily.values())
        else:
            return [
                float(v) for log in logs
                if (v := (log.data or {}).get(field)) is not None
            ]

    elif source == "food_entry":
        entries = (await session.execute(
            select(FoodEntry).where(and_(
                FoodEntry.user_id == user_id,
                FoodEntry.logged_at >= since,
            )).order_by(FoodEntry.logged_date)
        )).scalars().all()

        daily: dict[str, float] = {}
        for e in entries:
            d = e.logged_date.isoformat()
            val = getattr(e, field)
            if val is not None:
                daily[d] = daily.get(d, 0) + float(val)
        return list(daily.values())

    return []


def _build_label(
    metric_key: str,
    current_value: float,
    rank_position: int,
    rank_total: int,
    z_score: float,
    mean_30d: float,
    history: list[float],
) -> str:
    """Build a human-readable context label for an anomaly."""
    metric_labels = {
        "sodium_mg": "Natrium-Aufnahme",
        "calories": "Kalorienzufuhr",
        "sleep_hours": "Schlafdauer",
        "sleep_quality": "Schlafqualität",
        "mood": "Stimmungswert",
        "water_liters": "Wasseraufnahme",
        "steps": "Schrittzahl",
        "hrv": "HRV",
        "protein_g": "Proteinaufnahme",
    }
    label_name = metric_labels.get(metric_key, metric_key)

    if rank_total < 3:
        return f"Zu wenig Daten für {label_name}-Vergleich"

    # Find how many days back since a higher value
    if rank_position == 1:
        days_since = len(history)
        if days_since >= 90:
            return f"Höchste {label_name} aller Zeiten (seit {days_since}+ Tagen)"
        elif days_since >= 30:
            return f"Höchste {label_name} in {days_since} Tagen"
        elif days_since >= 14:
            return f"Höchste {label_name} in {days_since} Tagen"
        else:
            return f"Höchste {label_name} in {days_since} Tagen"
    elif rank_position == rank_total:
        days_since = len(history)
        return f"Niedrigste {label_name} in {days_since} Tagen"
    elif z_score > 2.0:
        return f"{label_name} {abs(z_score):.1f}x über deinem 30-Tage-Durchschnitt ({mean_30d:.0f})"
    elif z_score > 1.5:
        pct_above = int(((current_value - mean_30d) / mean_30d) * 100)
        return f"{label_name} {pct_above}% über deinem 30-Tage-Durchschnitt"
    elif z_score < -2.0:
        return f"{label_name} deutlich unter deinem 30-Tage-Durchschnitt"
    elif abs(z_score) < 0.5:
        return f"{label_name} im normalen Bereich (Ø {mean_30d:.0f})"
    else:
        pct = int(((current_value - mean_30d) / mean_30d) * 100)
        direction = "über" if pct > 0 else "unter"
        return f"{label_name} {abs(pct)}% {direction} deinem Durchschnitt"
