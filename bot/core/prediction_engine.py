"""Predictive Analytics Engine — Vorhersagen für Ziele, Budget, Routinen & Energie.

Nutzt lineare Regression und statistische Musteranalyse, um:
  - Zielerreichungs-Zeitpunkte vorherzusagen
  - Monatsend-Budget zu projizieren
  - Routine-Ausfälle zu prognostizieren
  - Energielevel vorherzusagen
"""
from __future__ import annotations

import logging
import math
from collections import defaultdict
from datetime import date, datetime, timedelta
from statistics import mean, stdev, linear_regression
from typing import Optional

from sqlalchemy import and_, func, select, extract
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import (
    Prediction, KeyResult, Log, FinancialTransaction, Budget,
    Routine, RoutineCompletion, DailyContext,
)

logger = logging.getLogger(__name__)

DAY_NAMES_DE = [
    "Montag", "Dienstag", "Mittwoch", "Donnerstag",
    "Freitag", "Samstag", "Sonntag",
]

# ─── Helpers ──────────────────────────────────────────────────────────────────


def _safe_linear_regression(
    xs: list[float], ys: list[float],
) -> tuple[float, float] | None:
    """Return (slope, intercept) or None if regression is impossible."""
    if len(xs) < 2 or len(ys) < 2 or len(xs) != len(ys):
        return None
    # All x values identical → no trend
    if all(x == xs[0] for x in xs):
        return None
    try:
        slope, intercept = linear_regression(xs, ys)
        return slope, intercept
    except Exception:
        return None


def _r_squared(xs: list[float], ys: list[float], slope: float, intercept: float) -> float:
    """Compute R² (coefficient of determination)."""
    if len(ys) < 2:
        return 0.0
    y_mean = mean(ys)
    ss_tot = sum((y - y_mean) ** 2 for y in ys)
    if ss_tot == 0:
        return 1.0
    ss_res = sum((y - (slope * x + intercept)) ** 2 for x, x in zip(xs, ys))
    # Fix: use correct variable names
    ss_res = sum((ys[i] - (slope * xs[i] + intercept)) ** 2 for i in range(len(xs)))
    return max(0.0, 1.0 - ss_res / ss_tot)


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


# ─── 1. Goal Completion Prediction ───────────────────────────────────────────


async def predict_goal_completion(
    session: AsyncSession,
    user_id: int,
    key_result_id: int,
) -> dict:
    """Lineare Regression auf KR-Fortschrittslogs → Vorhersage der Zielerreichung."""
    kr = await session.get(KeyResult, key_result_id)
    if not kr or kr.user_id != user_id:
        return {
            "kr_id": key_result_id,
            "kr_title": "Unbekannt",
            "current_value": 0.0,
            "target_value": 0.0,
            "predicted_completion_date": None,
            "confidence": 0.0,
            "pace": "stalled",
            "days_remaining": 0,
            "message": "Key Result nicht gefunden.",
        }

    target_value = kr.target_value or 0.0
    current_value = kr.current_value or 0.0

    # Already completed
    if kr.status == "completed" or (target_value > 0 and current_value >= target_value):
        return {
            "kr_id": kr.id,
            "kr_title": kr.title,
            "current_value": current_value,
            "target_value": target_value,
            "predicted_completion_date": date.today().isoformat(),
            "confidence": 1.0,
            "pace": "ahead",
            "days_remaining": 0,
            "message": f"'{kr.title}' ist bereits abgeschlossen!",
        }

    # Fetch progress logs
    stmt = (
        select(Log)
        .where(
            and_(
                Log.user_id == user_id,
                Log.key_result_id == key_result_id,
                Log.log_type == "progress",
            )
        )
        .order_by(Log.logged_at.asc())
    )
    result = await session.execute(stmt)
    logs = list(result.scalars().all())

    if len(logs) < 2:
        return {
            "kr_id": kr.id,
            "kr_title": kr.title,
            "current_value": current_value,
            "target_value": target_value,
            "predicted_completion_date": None,
            "confidence": 0.0,
            "pace": "stalled",
            "days_remaining": -1,
            "message": f"Zu wenig Daten für '{kr.title}' — mindestens 2 Fortschritts-Logs nötig.",
        }

    # Build time series: day offset from first log → value
    base_date = logs[0].logged_at.date() if isinstance(logs[0].logged_at, datetime) else logs[0].logged_at
    xs: list[float] = []
    ys: list[float] = []
    for log in logs:
        log_date = log.logged_at.date() if isinstance(log.logged_at, datetime) else log.logged_at
        day_offset = (log_date - base_date).days
        value = log.data.get("value", log.data.get("new_value", 0)) if isinstance(log.data, dict) else 0
        xs.append(float(day_offset))
        ys.append(float(value))

    reg = _safe_linear_regression(xs, ys)
    if reg is None or reg[0] <= 0:
        # No positive trend
        pace = "stalled"
        return {
            "kr_id": kr.id,
            "kr_title": kr.title,
            "current_value": current_value,
            "target_value": target_value,
            "predicted_completion_date": None,
            "confidence": 0.0,
            "pace": pace,
            "days_remaining": -1,
            "message": f"'{kr.title}': Kein positiver Trend erkennbar — Fortschritt stagniert.",
        }

    slope, intercept = reg
    r2 = _r_squared(xs, ys, slope, intercept)
    confidence = _clamp(r2, 0.0, 1.0)

    # Predict when target will be reached
    if target_value > 0:
        days_to_target = (target_value - intercept) / slope
        predicted_date = base_date + timedelta(days=int(math.ceil(days_to_target)))
    else:
        predicted_date = None
        days_to_target = -1

    today = date.today()
    days_remaining = (predicted_date - today).days if predicted_date else -1

    # Determine pace relative to target_date
    if kr.target_date and predicted_date:
        if predicted_date <= kr.target_date - timedelta(days=7):
            pace = "ahead"
        elif predicted_date <= kr.target_date + timedelta(days=7):
            pace = "on_track"
        else:
            pace = "behind"
    elif predicted_date:
        pace = "on_track"
    else:
        pace = "stalled"

    # Build message
    if pace == "ahead":
        msg = f"'{kr.title}': Voraussichtlich am {predicted_date.strftime('%d.%m.%Y')} erreicht — vor dem Ziel!"
    elif pace == "on_track":
        msg = f"'{kr.title}': Auf Kurs — voraussichtlich am {predicted_date.strftime('%d.%m.%Y')} erreicht."
    elif pace == "behind":
        msg = f"'{kr.title}': Hinter dem Zeitplan — voraussichtlich erst am {predicted_date.strftime('%d.%m.%Y')}."
    else:
        msg = f"'{kr.title}': Fortschritt stagniert."

    return {
        "kr_id": kr.id,
        "kr_title": kr.title,
        "current_value": current_value,
        "target_value": target_value,
        "predicted_completion_date": predicted_date.isoformat() if predicted_date else None,
        "confidence": round(confidence, 2),
        "pace": pace,
        "days_remaining": days_remaining,
        "message": msg,
    }


# ─── 2. Budget Forecast ──────────────────────────────────────────────────────


async def predict_budget_forecast(
    session: AsyncSession,
    user_id: int,
) -> dict:
    """Analysiert Ausgaben der letzten 3 Monate und projiziert Monatsend-Totale."""
    today = date.today()
    current_month_start = today.replace(day=1)
    three_months_ago = (current_month_start - timedelta(days=90)).replace(day=1)

    # Days elapsed and remaining in current month
    days_elapsed = today.day
    if today.month == 12:
        month_end = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
    else:
        month_end = today.replace(month=today.month + 1, day=1) - timedelta(days=1)
    days_in_month = month_end.day

    # Fetch current month expenses
    stmt_current = (
        select(
            FinancialTransaction.category,
            func.sum(FinancialTransaction.amount).label("total"),
        )
        .where(
            and_(
                FinancialTransaction.user_id == user_id,
                FinancialTransaction.type == "expense",
                FinancialTransaction.transaction_date >= current_month_start,
                FinancialTransaction.transaction_date <= today,
            )
        )
        .group_by(FinancialTransaction.category)
    )
    result_current = await session.execute(stmt_current)
    current_spending: dict[str, float] = {
        row.category: float(row.total) for row in result_current
    }

    # Fetch historical monthly averages (previous 3 months)
    stmt_hist = (
        select(
            FinancialTransaction.category,
            extract("year", FinancialTransaction.transaction_date).label("yr"),
            extract("month", FinancialTransaction.transaction_date).label("mo"),
            func.sum(FinancialTransaction.amount).label("total"),
        )
        .where(
            and_(
                FinancialTransaction.user_id == user_id,
                FinancialTransaction.type == "expense",
                FinancialTransaction.transaction_date >= three_months_ago,
                FinancialTransaction.transaction_date < current_month_start,
            )
        )
        .group_by(
            FinancialTransaction.category,
            extract("year", FinancialTransaction.transaction_date),
            extract("month", FinancialTransaction.transaction_date),
        )
    )
    result_hist = await session.execute(stmt_hist)
    hist_by_cat: dict[str, list[float]] = defaultdict(list)
    for row in result_hist:
        hist_by_cat[row.category].append(float(row.total))

    # Fetch budgets
    stmt_budgets = select(Budget).where(Budget.user_id == user_id)
    result_budgets = await session.execute(stmt_budgets)
    budgets: dict[str, float] = {
        b.category: b.monthly_limit for b in result_budgets.scalars().all()
    }

    # Project per category
    all_categories = set(current_spending.keys()) | set(budgets.keys()) | set(hist_by_cat.keys())
    categories_result: list[dict] = []
    projected_total = 0.0
    budget_total = 0.0

    for cat in sorted(all_categories):
        spent = current_spending.get(cat, 0.0)
        budget_limit = budgets.get(cat, 0.0)
        hist_avg = mean(hist_by_cat[cat]) if hist_by_cat.get(cat) else 0.0

        # Projection: linear extrapolation of current spending rate,
        # weighted with historical average
        if days_elapsed > 0:
            daily_rate = spent / days_elapsed
            linear_projection = daily_rate * days_in_month
        else:
            linear_projection = 0.0

        if hist_avg > 0 and linear_projection > 0:
            # Weight: 60% current pace, 40% historical average
            projected = 0.6 * linear_projection + 0.4 * hist_avg
        elif linear_projection > 0:
            projected = linear_projection
        else:
            projected = hist_avg

        projected = round(projected, 2)
        projected_total += projected
        budget_total += budget_limit

        alert = projected > budget_limit > 0
        if alert:
            over_pct = ((projected - budget_limit) / budget_limit) * 100
            msg = f"{cat.capitalize()}: Voraussichtlich {over_pct:.0f}% über Budget ({projected:.2f}€ vs. {budget_limit:.2f}€)."
        elif budget_limit > 0:
            msg = f"{cat.capitalize()}: Im Rahmen — {projected:.2f}€ von {budget_limit:.2f}€ Budget."
        else:
            msg = f"{cat.capitalize()}: {projected:.2f}€ projiziert (kein Budget gesetzt)."

        categories_result.append({
            "category": cat,
            "spent": round(spent, 2),
            "budget": round(budget_limit, 2),
            "projected": projected,
            "alert": alert,
            "message": msg,
        })

    surplus_deficit = round(budget_total - projected_total, 2)

    return {
        "month": today.strftime("%Y-%m"),
        "projected_total": round(projected_total, 2),
        "budget_total": round(budget_total, 2),
        "projected_surplus_deficit": surplus_deficit,
        "categories": categories_result,
    }


# ─── 3. Routine Break Prediction ─────────────────────────────────────────────


async def predict_routine_breaks(
    session: AsyncSession,
    user_id: int,
) -> list[dict]:
    """Analysiert Routine-Completion-Muster → welche Routinen diese Woche ausfallen könnten."""
    today = date.today()
    analysis_start = today - timedelta(days=42)  # 6 weeks of data

    # Fetch active routines
    stmt_routines = select(Routine).where(
        and_(Routine.user_id == user_id, Routine.status == "active")
    )
    result_routines = await session.execute(stmt_routines)
    routines = list(result_routines.scalars().all())

    if not routines:
        return []

    # Fetch completions in analysis window
    routine_ids = [r.id for r in routines]
    stmt_completions = (
        select(RoutineCompletion)
        .where(
            and_(
                RoutineCompletion.user_id == user_id,
                RoutineCompletion.routine_id.in_(routine_ids),
                RoutineCompletion.completed_at >= datetime.combine(analysis_start, datetime.min.time()),
            )
        )
    )
    result_completions = await session.execute(stmt_completions)
    completions = list(result_completions.scalars().all())

    # Build per-routine, per-weekday completion rates
    comp_by_routine: dict[int, dict[int, int]] = defaultdict(lambda: defaultdict(int))
    for c in completions:
        c_date = c.completed_at.date() if isinstance(c.completed_at, datetime) else c.completed_at
        weekday = c_date.weekday()  # 0=Monday
        comp_by_routine[c.routine_id][weekday] += 1

    # Count weeks per weekday in analysis window
    weeks_per_weekday: dict[int, int] = defaultdict(int)
    d = analysis_start
    while d <= today:
        weeks_per_weekday[d.weekday()] += 1
        d += timedelta(days=1)
    # Convert to week count (divide by occurrence count → each weekday appears ~6 times)
    # Actually weeks_per_weekday already counts days, so each weekday appears analysis_days/7 times
    total_weeks = (today - analysis_start).days / 7.0

    # Determine upcoming week days (rest of this week + next 7 if needed)
    predictions: list[dict] = []

    for routine in routines:
        r_completions = comp_by_routine.get(routine.id, {})
        total_completions = sum(r_completions.values())

        # Recent trend: completions in last 2 weeks vs. 2 weeks before that
        recent_cutoff = today - timedelta(days=14)
        older_cutoff = today - timedelta(days=28)
        recent_count = 0
        older_count = 0
        for c in completions:
            if c.routine_id != routine.id:
                continue
            c_date = c.completed_at.date() if isinstance(c.completed_at, datetime) else c.completed_at
            if c_date >= recent_cutoff:
                recent_count += 1
            elif c_date >= older_cutoff:
                older_count += 1

        # Trend factor: declining = higher skip probability
        if older_count > 0:
            trend_factor = recent_count / older_count
        elif recent_count > 0:
            trend_factor = 1.0
        else:
            trend_factor = 0.5  # No data → assume risky

        # Find the weakest day for this routine in the coming week
        worst_day: int | None = None
        worst_prob: float = 0.0

        for weekday in range(7):
            completed_on_day = r_completions.get(weekday, 0)
            expected_on_day = max(total_weeks, 1.0)
            completion_rate = completed_on_day / expected_on_day
            skip_rate = 1.0 - min(completion_rate, 1.0)

            # Adjust by trend
            adjusted_skip = skip_rate * (1.0 / max(trend_factor, 0.1))
            adjusted_skip = _clamp(adjusted_skip, 0.0, 0.99)

            if adjusted_skip > worst_prob:
                worst_prob = adjusted_skip
                worst_day = weekday

        if worst_day is not None and worst_prob >= 0.3:
            # Generate recommendation
            if worst_prob >= 0.7:
                rec = f"Hohe Ausfallgefahr! Plane '{routine.title}' bewusst ein und setze dir eine Erinnerung."
            elif worst_prob >= 0.5:
                rec = f"'{routine.title}' fällt häufig aus. Verknüpfe sie mit einer bestehenden Gewohnheit."
            else:
                rec = f"Leicht erhöhtes Risiko für '{routine.title}'. Bleib dran!"

            predictions.append({
                "routine_id": routine.id,
                "routine_title": routine.title,
                "risk_day": DAY_NAMES_DE[worst_day],
                "skip_probability": round(worst_prob, 2),
                "recommendation": rec,
            })

    # Sort by skip probability descending
    predictions.sort(key=lambda p: p["skip_probability"], reverse=True)
    return predictions


# ─── 4. Energy Level Prediction ──────────────────────────────────────────────


async def predict_energy_level(
    session: AsyncSession,
    user_id: int,
    target_date: date | None = None,
) -> dict:
    """Vorhersage des Energielevels basierend auf historischen Mustern."""
    if target_date is None:
        target_date = date.today() + timedelta(days=1)

    analysis_start = target_date - timedelta(days=60)

    # Fetch DailyContext data
    stmt_ctx = (
        select(DailyContext)
        .where(
            and_(
                DailyContext.user_id == user_id,
                DailyContext.date >= analysis_start,
                DailyContext.date < target_date,
                DailyContext.energy.isnot(None),
            )
        )
        .order_by(DailyContext.date.asc())
    )
    result_ctx = await session.execute(stmt_ctx)
    contexts = list(result_ctx.scalars().all())

    if len(contexts) < 3:
        return {
            "predicted_energy": 5,
            "confidence": 0.0,
            "factors": [],
            "recommendation": "Zu wenig Daten für eine Vorhersage — trage täglich dein Energielevel ein.",
        }

    # Analyze energy by day of week
    energy_by_weekday: dict[int, list[int]] = defaultdict(list)
    all_energies: list[int] = []
    for ctx in contexts:
        if ctx.energy is not None:
            energy_by_weekday[ctx.date.weekday()].append(ctx.energy)
            all_energies.append(ctx.energy)

    avg_energy = mean(all_energies) if all_energies else 5.0
    target_weekday = target_date.weekday()

    factors: list[dict] = []
    predicted = avg_energy

    # Factor 1: Day of week pattern
    weekday_energies = energy_by_weekday.get(target_weekday, [])
    if weekday_energies:
        weekday_avg = mean(weekday_energies)
        diff = weekday_avg - avg_energy
        if abs(diff) >= 0.3:
            direction = "positive" if diff > 0 else "negative"
            factors.append({
                "factor": f"Wochentagsmuster ({DAY_NAMES_DE[target_weekday]})",
                "impact": f"{diff:+.1f} Punkte",
                "direction": direction,
            })
            predicted += diff * 0.4  # weighted

    # Factor 2: Recent trend (last 7 days)
    recent_contexts = [c for c in contexts if c.date >= target_date - timedelta(days=7)]
    if recent_contexts:
        recent_avg = mean([c.energy for c in recent_contexts if c.energy is not None])
        trend_diff = recent_avg - avg_energy
        if abs(trend_diff) >= 0.3:
            direction = "positive" if trend_diff > 0 else "negative"
            factors.append({
                "factor": "Aktueller Trend (letzte 7 Tage)",
                "impact": f"{trend_diff:+.1f} Punkte",
                "direction": direction,
            })
            predicted += trend_diff * 0.3

    # Factor 3: Check if previous day had workout (from logs)
    prev_date = target_date - timedelta(days=1)
    stmt_workout = (
        select(func.count())
        .select_from(Log)
        .where(
            and_(
                Log.user_id == user_id,
                Log.log_type == "workout",
                func.date(Log.logged_at) == prev_date,
            )
        )
    )
    workout_result = await session.execute(stmt_workout)
    had_workout = (workout_result.scalar() or 0) > 0

    if had_workout:
        # Check historical: energy after workout days
        workout_dates_stmt = (
            select(func.date(Log.logged_at).label("d"))
            .where(
                and_(
                    Log.user_id == user_id,
                    Log.log_type == "workout",
                    Log.logged_at >= datetime.combine(analysis_start, datetime.min.time()),
                )
            )
            .distinct()
        )
        wr = await session.execute(workout_dates_stmt)
        workout_dates = {row.d for row in wr}

        post_workout_energies = []
        for ctx in contexts:
            prev = ctx.date - timedelta(days=1)
            if prev in workout_dates and ctx.energy is not None:
                post_workout_energies.append(ctx.energy)

        if post_workout_energies:
            pw_avg = mean(post_workout_energies)
            pw_diff = pw_avg - avg_energy
            direction = "positive" if pw_diff > 0 else "negative"
            factors.append({
                "factor": "Training am Vortag",
                "impact": f"{pw_diff:+.1f} Punkte",
                "direction": direction,
            })
            predicted += pw_diff * 0.2

    # Factor 4: Routine completions yesterday
    stmt_rc = (
        select(func.count())
        .select_from(RoutineCompletion)
        .where(
            and_(
                RoutineCompletion.user_id == user_id,
                func.date(RoutineCompletion.completed_at) == prev_date,
            )
        )
    )
    rc_result = await session.execute(stmt_rc)
    rc_count = rc_result.scalar() or 0

    if rc_count >= 3:
        factors.append({
            "factor": f"Routinen gestern ({rc_count} erledigt)",
            "impact": "+0.5 Punkte",
            "direction": "positive",
        })
        predicted += 0.5
    elif rc_count == 0:
        factors.append({
            "factor": "Keine Routinen gestern",
            "impact": "-0.5 Punkte",
            "direction": "negative",
        })
        predicted -= 0.5

    # Clamp and round
    predicted_int = int(round(_clamp(predicted, 1.0, 10.0)))

    # Confidence based on data amount and consistency
    data_factor = min(len(contexts) / 30.0, 1.0)
    if len(all_energies) >= 2:
        try:
            energy_stdev = stdev(all_energies)
        except Exception:
            energy_stdev = 2.0
        consistency_factor = max(0.0, 1.0 - energy_stdev / 5.0)
    else:
        consistency_factor = 0.3
    confidence = round(_clamp(data_factor * 0.6 + consistency_factor * 0.4, 0.0, 1.0), 2)

    # Recommendation
    if predicted_int >= 7:
        rec = "Guter Energietag erwartet — nutze ihn für anspruchsvolle Aufgaben!"
    elif predicted_int >= 5:
        rec = "Normales Energielevel erwartet — plane einen ausgewogenen Tag."
    elif predicted_int >= 3:
        rec = "Eher niedriges Energielevel — priorisiere und plane Pausen ein."
    else:
        rec = "Sehr niedriges Energielevel erwartet — fokussiere dich auf das Nötigste und erhole dich."

    return {
        "predicted_energy": predicted_int,
        "confidence": confidence,
        "factors": factors,
        "recommendation": rec,
    }


# ─── 5. Run All Predictions ──────────────────────────────────────────────────


async def run_all_predictions(
    session: AsyncSession,
    user_id: int,
) -> dict:
    """Führt alle Vorhersage-Engines aus und speichert Ergebnisse als Prediction-Datensätze."""
    # Deactivate old predictions
    stmt_deactivate = (
        select(Prediction)
        .where(and_(Prediction.user_id == user_id, Prediction.is_active == True))  # noqa: E712
    )
    old_preds = await session.execute(stmt_deactivate)
    for pred in old_preds.scalars().all():
        pred.is_active = False

    results: dict = {
        "goal_predictions": [],
        "budget_forecast": None,
        "routine_risks": [],
        "energy_prediction": None,
        "errors": [],
    }

    # 1. Goal completion for all active KRs
    try:
        stmt_krs = select(KeyResult).where(
            and_(KeyResult.user_id == user_id, KeyResult.status == "active")
        )
        kr_result = await session.execute(stmt_krs)
        key_results = list(kr_result.scalars().all())

        for kr in key_results:
            try:
                pred = await predict_goal_completion(session, user_id, kr.id)
                results["goal_predictions"].append(pred)

                # Store as Prediction record
                prediction_record = Prediction(
                    user_id=user_id,
                    prediction_type="goal_completion",
                    entity_type="key_result",
                    entity_id=kr.id,
                    predicted_value=kr.target_value,
                    predicted_date=(
                        date.fromisoformat(pred["predicted_completion_date"])
                        if pred["predicted_completion_date"]
                        else None
                    ),
                    confidence=pred["confidence"],
                    explanation=pred["message"],
                    data=pred,
                    is_active=True,
                )
                session.add(prediction_record)
            except Exception as e:
                logger.error("Fehler bei Goal-Prediction für KR %d: %s", kr.id, e)
                results["errors"].append(f"KR {kr.id}: {e}")
    except Exception as e:
        logger.error("Fehler beim Laden der Key Results: %s", e)
        results["errors"].append(f"Key Results: {e}")

    # 2. Budget forecast
    try:
        budget = await predict_budget_forecast(session, user_id)
        results["budget_forecast"] = budget

        prediction_record = Prediction(
            user_id=user_id,
            prediction_type="budget_forecast",
            entity_type="budget",
            entity_id=None,
            predicted_value=budget["projected_total"],
            predicted_date=None,
            confidence=0.7,  # Budget projections are generally reliable
            explanation=(
                f"Projiziert: {budget['projected_total']:.2f}€ "
                f"(Budget: {budget['budget_total']:.2f}€)"
            ),
            data=budget,
            is_active=True,
        )
        session.add(prediction_record)
    except Exception as e:
        logger.error("Fehler bei Budget-Forecast: %s", e)
        results["errors"].append(f"Budget: {e}")

    # 3. Routine break predictions
    try:
        routine_risks = await predict_routine_breaks(session, user_id)
        results["routine_risks"] = routine_risks

        for risk in routine_risks:
            prediction_record = Prediction(
                user_id=user_id,
                prediction_type="routine_break",
                entity_type="routine",
                entity_id=risk["routine_id"],
                predicted_value=risk["skip_probability"],
                predicted_date=None,
                confidence=risk["skip_probability"],
                explanation=risk["recommendation"],
                data=risk,
                is_active=True,
            )
            session.add(prediction_record)
    except Exception as e:
        logger.error("Fehler bei Routine-Prediction: %s", e)
        results["errors"].append(f"Routinen: {e}")

    # 4. Energy prediction
    try:
        energy = await predict_energy_level(session, user_id)
        results["energy_prediction"] = energy

        prediction_record = Prediction(
            user_id=user_id,
            prediction_type="energy_level",
            entity_type="daily_context",
            entity_id=None,
            predicted_value=float(energy["predicted_energy"]),
            predicted_date=date.today() + timedelta(days=1),
            confidence=energy["confidence"],
            explanation=energy["recommendation"],
            data=energy,
            is_active=True,
        )
        session.add(prediction_record)
    except Exception as e:
        logger.error("Fehler bei Energy-Prediction: %s", e)
        results["errors"].append(f"Energie: {e}")

    await session.flush()
    return results


# ─── 6. Prediction Summary for AI Prompt ─────────────────────────────────────


async def get_prediction_summary(
    session: AsyncSession,
    user_id: int,
) -> str:
    """Gibt einen Kontext-String (max 12 Zeilen) mit aktiven Vorhersagen zurück."""
    stmt = (
        select(Prediction)
        .where(
            and_(
                Prediction.user_id == user_id,
                Prediction.is_active == True,  # noqa: E712
                Prediction.created_at >= datetime.combine(
                    date.today() - timedelta(days=2), datetime.min.time()
                ),
            )
        )
        .order_by(Prediction.created_at.desc())
        .limit(20)
    )
    result = await session.execute(stmt)
    predictions = list(result.scalars().all())

    if not predictions:
        return ""

    lines: list[str] = ["📊 Vorhersagen:"]

    # Group by type
    by_type: dict[str, list[Prediction]] = defaultdict(list)
    for p in predictions:
        by_type[p.prediction_type].append(p)

    # Goal predictions (max 3)
    goal_preds = by_type.get("goal_completion", [])[:3]
    for p in goal_preds:
        data = p.data or {}
        pace = data.get("pace", "")
        icon = {"ahead": "🟢", "on_track": "🟡", "behind": "🔴", "stalled": "⚪"}.get(pace, "⚪")
        title = data.get("kr_title", "?")
        pred_date = data.get("predicted_completion_date", "?")
        lines.append(f"  {icon} {title}: {pace} (→ {pred_date})")

    # Budget (max 1)
    budget_preds = by_type.get("budget_forecast", [])[:1]
    for p in budget_preds:
        data = p.data or {}
        surplus = data.get("projected_surplus_deficit", 0)
        icon = "🟢" if surplus >= 0 else "🔴"
        alerts = [c for c in data.get("categories", []) if c.get("alert")]
        alert_str = f" — {len(alerts)} Kategorie(n) über Budget" if alerts else ""
        lines.append(f"  {icon} Budget: {surplus:+.0f}€{alert_str}")

    # Routine risks (max 2)
    routine_preds = by_type.get("routine_break", [])[:2]
    for p in routine_preds:
        data = p.data or {}
        prob = data.get("skip_probability", 0)
        title = data.get("routine_title", "?")
        day = data.get("risk_day", "?")
        lines.append(f"  ⚠️ {title}: {prob:.0%} Ausfallrisiko am {day}")

    # Energy (max 1)
    energy_preds = by_type.get("energy_level", [])[:1]
    for p in energy_preds:
        data = p.data or {}
        energy = data.get("predicted_energy", "?")
        lines.append(f"  ⚡ Energie morgen: {energy}/10")

    # Cap at 12 lines
    return "\n".join(lines[:12])
