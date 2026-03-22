"""Cross-metric correlation engine — discovers health/behavior relationships.

Analyzes 30 days of data to find correlations like:
  "Wenn du >7h schläfst, ist dein Mood am nächsten Tag 1.8 Punkte höher"
  "An Trainingstagen ist deine Energie 2.1 Punkte höher"

Returns UserInsight-compatible dicts with insight_type="correlation".
"""
from __future__ import annotations

import logging
import math
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import DailyContext, FoodEntry, Log, RoutineCompletion

logger = logging.getLogger(__name__)

ANALYSIS_DAYS = 30
MIN_PAIRS = 7  # Minimum overlapping data points for a valid correlation
MIN_ABS_R = 0.3  # Minimum |r| to report


async def run_correlation_analysis(
    session: AsyncSession,
    user_id: int,
) -> list[dict]:
    """Run all cross-metric correlations and return insight dicts."""
    since = datetime.combine(date.today() - timedelta(days=ANALYSIS_DAYS), datetime.min.time())

    # Gather data vectors indexed by date string
    mood = await _get_mood_by_date(session, user_id, since)
    sleep = await _get_sleep_by_date(session, user_id, since)
    steps = await _get_steps_by_date(session, user_id, since)
    workout = await _get_workout_days(session, user_id, since)
    water = await _get_water_by_date(session, user_id, since)
    energy = await _get_energy_by_date(session, user_id, since)
    routines = await _get_routine_counts_by_date(session, user_id, since)

    insights: list[dict] = []

    # Gather nutrition vectors
    sodium = await _get_nutrition_metric_by_date(session, user_id, since, "sodium_mg")
    calories_food = await _get_nutrition_metric_by_date(session, user_id, since, "calories")
    protein = await _get_nutrition_metric_by_date(session, user_id, since, "protein_g")

    # ── Correlation pairs ────────────────────────────────────────────────────

    # Sleep → Mood (next day, lagged)
    _check_lagged(insights, sleep, mood, "Schlaf (Stunden)", "Mood", lag=1,
                  template_pos="Wenn du mehr schläfst, ist dein Mood am nächsten Tag durchschnittlich {diff:.1f} Punkte höher",
                  template_neg="Mehr Schlaf korreliert mit niedrigerem Mood am Folgetag ({diff:.1f} Punkte)",
                  threshold_fn=lambda vals: 7.0, label_above=">7h Schlaf", label_below="<7h Schlaf")

    # Sleep → Energy (next day)
    _check_lagged(insights, sleep, energy, "Schlaf", "Energie", lag=1,
                  template_pos="Nach >7h Schlaf ist deine Energie am nächsten Tag {diff:.1f} Punkte höher",
                  template_neg="Mehr Schlaf korreliert mit weniger Energie ({diff:.1f})",
                  threshold_fn=lambda vals: 7.0, label_above=">7h", label_below="<7h")

    # Steps → Mood (same day)
    _check_split(insights, steps, mood, "Schritte", "Mood",
                 template_pos="An Tagen mit >8000 Schritten ist dein Mood {diff:.1f} Punkte höher",
                 template_neg="Mehr Schritte korrelieren mit niedrigerem Mood ({diff:.1f})",
                 threshold_fn=lambda vals: 8000)

    # Workout → Mood (same day)
    _check_binary(insights, workout, mood, "Training", "Mood",
                  template_pos="An Trainingstagen ist dein Mood {diff:.1f} Punkte höher ({avg_yes:.1f} vs {avg_no:.1f})",
                  template_neg="An Trainingstagen ist dein Mood {diff:.1f} Punkte niedriger")

    # Workout → Mood (next day)
    _check_binary_lagged(insights, workout, mood, "Training", "Mood (Folgetag)", lag=1,
                         template_pos="Nach dem Training ist dein Mood am Folgetag {diff:.1f} Punkte höher",
                         template_neg="Nach dem Training ist dein Mood am Folgetag {diff:.1f} Punkte niedriger")

    # Water → Energy (same day)
    _check_split(insights, water, energy, "Wasser (Liter)", "Energie",
                 template_pos="An Tagen mit >2L Wasser ist deine Energie {diff:.1f} Punkte höher",
                 template_neg="Mehr Wasser korreliert mit weniger Energie ({diff:.1f})",
                 threshold_fn=lambda vals: 2.0)

    # Routine completions → Mood
    _check_pearson(insights, routines, mood, "Routinen abgeschlossen", "Mood",
                   template="Mehr abgeschlossene Routinen korrelieren mit höherem Mood (r={r:.2f})")

    # Workout → Energy (same day)
    _check_binary(insights, workout, energy, "Training", "Energie",
                  template_pos="An Trainingstagen ist deine Energie {diff:.1f} Punkte höher ({avg_yes:.1f} vs {avg_no:.1f})",
                  template_neg="An Trainingstagen ist deine Energie {diff:.1f} Punkte niedriger")

    # ── Nutrition correlations ────────────────────────────────────────────────

    # Sodium → Sleep next day (the key example from the vision!)
    if sodium:
        _check_lagged(insights, sodium, sleep, "Natrium (mg)", "Schlaf (Stunden)", lag=1,
                      template_pos="Nach niedrigem Natrium schläfst du am nächsten Tag {diff:.1f}h besser",
                      template_neg="Hohe Natriumaufnahme korreliert mit {diff:.1f}h weniger Schlaf am Folgetag",
                      threshold_fn=lambda vals: sorted(vals)[len(vals) // 2],  # median split
                      label_above="hohes Natrium", label_below="niedriges Natrium")

    # Sodium → Sleep quality next day
    if sodium:
        _check_lagged(insights, sodium, mood, "Natrium (mg)", "Mood (Folgetag)", lag=1,
                      template_pos="Niedrige Natriumaufnahme korreliert mit besserem Mood am Folgetag (+{diff:.1f})",
                      template_neg="Hohe Natriumaufnahme korreliert mit schlechterem Mood am Folgetag ({diff:.1f} Punkte)",
                      threshold_fn=lambda vals: sorted(vals)[len(vals) // 2],
                      label_above="hohes Natrium", label_below="niedriges Natrium")

    # Calories → Mood (same day)
    if calories_food:
        _check_pearson(insights, calories_food, mood, "Kalorien", "Mood",
                       template="Kalorienzufuhr korreliert mit Mood (r={r:.2f})")

    # Calories → Energy (same day)
    if calories_food:
        _check_pearson(insights, calories_food, energy, "Kalorien", "Energie",
                       template="Kalorienzufuhr korreliert mit Energielevel (r={r:.2f})")

    # Protein → Energy (same day)
    if protein:
        _check_split(insights, protein, energy, "Protein (g)", "Energie",
                     template_pos="An Tagen mit viel Protein ist deine Energie {diff:.1f} Punkte höher",
                     template_neg="Mehr Protein korreliert mit weniger Energie ({diff:.1f})",
                     threshold_fn=lambda vals: sorted(vals)[len(vals) // 2])

    if insights:
        logger.info("Correlation analysis: %d insights for user %d", len(insights), user_id)
    return insights


# ── Data extraction helpers ──────────────────────────────────────────────────

async def _get_mood_by_date(session: AsyncSession, user_id: int, since: datetime) -> dict[str, float]:
    logs = (await session.execute(
        select(Log).where(and_(
            Log.user_id == user_id, Log.log_type == "mood", Log.logged_at >= since,
        ))
    )).scalars().all()
    result: dict[str, float] = {}
    for log in logs:
        score = (log.data or {}).get("score")
        if score:
            result[log.logged_at.strftime("%Y-%m-%d")] = float(score)
    return result


async def _get_sleep_by_date(session: AsyncSession, user_id: int, since: datetime) -> dict[str, float]:
    logs = (await session.execute(
        select(Log).where(and_(
            Log.user_id == user_id, Log.log_type == "sleep", Log.logged_at >= since,
        ))
    )).scalars().all()
    return {
        log.logged_at.strftime("%Y-%m-%d"): float((log.data or {}).get("hours", 0))
        for log in logs if (log.data or {}).get("hours")
    }


async def _get_steps_by_date(session: AsyncSession, user_id: int, since: datetime) -> dict[str, float]:
    logs = (await session.execute(
        select(Log).where(and_(
            Log.user_id == user_id, Log.log_type == "steps", Log.logged_at >= since,
        ))
    )).scalars().all()
    return {
        log.logged_at.strftime("%Y-%m-%d"): float((log.data or {}).get("count", 0))
        for log in logs if (log.data or {}).get("count")
    }


async def _get_workout_days(session: AsyncSession, user_id: int, since: datetime) -> dict[str, float]:
    """Binary: 1.0 for workout days, 0.0 for rest days."""
    logs = (await session.execute(
        select(Log).where(and_(
            Log.user_id == user_id, Log.log_type == "workout", Log.logged_at >= since,
        ))
    )).scalars().all()
    workout_dates = {log.logged_at.strftime("%Y-%m-%d") for log in logs}
    result: dict[str, float] = {}
    today = date.today()
    for i in range(ANALYSIS_DAYS):
        d = (today - timedelta(days=i)).isoformat()
        result[d] = 1.0 if d in workout_dates else 0.0
    return result


async def _get_water_by_date(session: AsyncSession, user_id: int, since: datetime) -> dict[str, float]:
    logs = (await session.execute(
        select(Log).where(and_(
            Log.user_id == user_id, Log.log_type == "water", Log.logged_at >= since,
        ))
    )).scalars().all()
    daily: dict[str, float] = defaultdict(float)
    for log in logs:
        d = log.logged_at.strftime("%Y-%m-%d")
        daily[d] += float((log.data or {}).get("amount", 0))
    return dict(daily)


async def _get_energy_by_date(session: AsyncSession, user_id: int, since: datetime) -> dict[str, float]:
    contexts = (await session.execute(
        select(DailyContext).where(and_(
            DailyContext.user_id == user_id,
            DailyContext.date >= since.date(),
        ))
    )).scalars().all()
    return {
        ctx.date.isoformat(): float(ctx.energy)
        for ctx in contexts if ctx.energy
    }


async def _get_nutrition_metric_by_date(
    session: AsyncSession,
    user_id: int,
    since: datetime,
    field: str,
) -> dict[str, float]:
    """Sum a nutrition metric (e.g. sodium_mg, calories) per day from food_entries."""
    entries = (await session.execute(
        select(FoodEntry).where(and_(
            FoodEntry.user_id == user_id,
            FoodEntry.logged_at >= since,
        ))
    )).scalars().all()
    daily: dict[str, float] = defaultdict(float)
    for e in entries:
        val = getattr(e, field, None)
        if val is not None:
            daily[e.logged_date.isoformat()] += float(val)
    return dict(daily) if daily else {}


async def _get_routine_counts_by_date(session: AsyncSession, user_id: int, since: datetime) -> dict[str, float]:
    completions = (await session.execute(
        select(RoutineCompletion).where(and_(
            RoutineCompletion.user_id == user_id,
            RoutineCompletion.completed_at >= since,
        ))
    )).scalars().all()
    daily: dict[str, float] = defaultdict(float)
    for comp in completions:
        daily[comp.completed_at.strftime("%Y-%m-%d")] += 1.0
    return dict(daily)


# ── Statistical helpers ──────────────────────────────────────────────────────

def _pearson(xs: list[float], ys: list[float]) -> Optional[float]:
    """Compute Pearson correlation coefficient. Returns None if insufficient data."""
    n = len(xs)
    if n < MIN_PAIRS or n != len(ys):
        return None
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    num = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    den_x = math.sqrt(sum((x - mean_x) ** 2 for x in xs))
    den_y = math.sqrt(sum((y - mean_y) ** 2 for y in ys))
    if den_x == 0 or den_y == 0:
        return None
    return num / (den_x * den_y)


def _aligned_pairs(
    a: dict[str, float],
    b: dict[str, float],
    lag: int = 0,
) -> tuple[list[float], list[float]]:
    """Get aligned value pairs. If lag>0, shift b forward by lag days."""
    xs, ys = [], []
    for date_str, val_a in a.items():
        if lag > 0:
            target_date = date.fromisoformat(date_str) + timedelta(days=lag)
            target_str = target_date.isoformat()
        else:
            target_str = date_str
        if target_str in b:
            xs.append(val_a)
            ys.append(b[target_str])
    return xs, ys


def _make_insight(
    title: str,
    description: str,
    r: Optional[float],
    data: dict,
) -> dict:
    strength = "stark" if abs(r or 0) >= 0.6 else "moderat" if abs(r or 0) >= 0.4 else "schwach"
    return {
        "type": "correlation",
        "title": title,
        "description": description,
        "data": {
            "correlation_r": round(r or 0, 3),
            "strength": strength,
            "n_pairs": data.get("n_pairs", 0),
            **data,
        },
    }


# ── Analysis functions ───────────────────────────────────────────────────────

def _check_pearson(
    insights: list[dict],
    a: dict[str, float],
    b: dict[str, float],
    name_a: str,
    name_b: str,
    template: str,
    lag: int = 0,
) -> None:
    xs, ys = _aligned_pairs(a, b, lag=lag)
    r = _pearson(xs, ys)
    if r is not None and abs(r) >= MIN_ABS_R:
        insights.append(_make_insight(
            f"{name_a} ↔ {name_b} (r={r:.2f})",
            template.format(r=r),
            r, {"n_pairs": len(xs), "metric_a": name_a, "metric_b": name_b},
        ))


def _check_lagged(
    insights: list[dict],
    a: dict[str, float],
    b: dict[str, float],
    name_a: str,
    name_b: str,
    lag: int,
    template_pos: str,
    template_neg: str,
    threshold_fn,
    label_above: str = "hoch",
    label_below: str = "niedrig",
) -> None:
    """Split a by threshold, compare b means (with lag)."""
    xs, ys = _aligned_pairs(a, b, lag=lag)
    if len(xs) < MIN_PAIRS:
        return
    threshold = threshold_fn(xs)
    above = [y for x, y in zip(xs, ys) if x >= threshold]
    below = [y for x, y in zip(xs, ys) if x < threshold]
    if len(above) < 3 or len(below) < 3:
        return
    avg_above = sum(above) / len(above)
    avg_below = sum(below) / len(below)
    diff = avg_above - avg_below
    if abs(diff) < 0.3:
        return
    r = _pearson(xs, ys)
    template = template_pos if diff > 0 else template_neg
    insights.append(_make_insight(
        f"{name_a} → {name_b}",
        template.format(diff=abs(diff), avg_above=avg_above, avg_below=avg_below),
        r, {"n_pairs": len(xs), "avg_above": round(avg_above, 2), "avg_below": round(avg_below, 2),
            "threshold": threshold, "diff": round(diff, 2)},
    ))


def _check_split(
    insights: list[dict],
    a: dict[str, float],
    b: dict[str, float],
    name_a: str,
    name_b: str,
    template_pos: str,
    template_neg: str,
    threshold_fn,
) -> None:
    """Same as _check_lagged but with lag=0."""
    _check_lagged(insights, a, b, name_a, name_b, lag=0,
                  template_pos=template_pos, template_neg=template_neg,
                  threshold_fn=threshold_fn)


def _check_binary(
    insights: list[dict],
    binary: dict[str, float],
    metric: dict[str, float],
    name_binary: str,
    name_metric: str,
    template_pos: str,
    template_neg: str,
) -> None:
    """Compare metric means on binary=1 vs binary=0 days."""
    yes_vals = [metric[d] for d in binary if binary[d] == 1.0 and d in metric]
    no_vals = [metric[d] for d in binary if binary[d] == 0.0 and d in metric]
    if len(yes_vals) < 3 or len(no_vals) < 3:
        return
    avg_yes = sum(yes_vals) / len(yes_vals)
    avg_no = sum(no_vals) / len(no_vals)
    diff = avg_yes - avg_no
    if abs(diff) < 0.3:
        return
    xs, ys = _aligned_pairs(binary, metric)
    r = _pearson(xs, ys)
    template = template_pos if diff > 0 else template_neg
    insights.append(_make_insight(
        f"{name_binary} → {name_metric}",
        template.format(diff=abs(diff), avg_yes=avg_yes, avg_no=avg_no),
        r, {"n_pairs": len(yes_vals) + len(no_vals), "avg_yes": round(avg_yes, 2),
            "avg_no": round(avg_no, 2), "diff": round(diff, 2)},
    ))


def _check_binary_lagged(
    insights: list[dict],
    binary: dict[str, float],
    metric: dict[str, float],
    name_binary: str,
    name_metric: str,
    lag: int,
    template_pos: str,
    template_neg: str,
) -> None:
    """Compare metric means on day+lag where binary=1 vs binary=0."""
    yes_vals, no_vals = [], []
    for d_str, val in binary.items():
        target = (date.fromisoformat(d_str) + timedelta(days=lag)).isoformat()
        if target in metric:
            if val == 1.0:
                yes_vals.append(metric[target])
            else:
                no_vals.append(metric[target])
    if len(yes_vals) < 3 or len(no_vals) < 3:
        return
    avg_yes = sum(yes_vals) / len(yes_vals)
    avg_no = sum(no_vals) / len(no_vals)
    diff = avg_yes - avg_no
    if abs(diff) < 0.3:
        return
    r = diff / max(abs(avg_yes), abs(avg_no), 1)  # normalized effect size
    template = template_pos if diff > 0 else template_neg
    insights.append(_make_insight(
        f"{name_binary} → {name_metric} (+{lag}d)",
        template.format(diff=abs(diff)),
        r, {"n_yes": len(yes_vals), "n_no": len(no_vals),
            "avg_yes": round(avg_yes, 2), "avg_no": round(avg_no, 2), "diff": round(diff, 2)},
    ))
