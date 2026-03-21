"""Adaptive Goal Adjustment Engine.

Analyses KR compliance, routine completion rates, and suggests target
adjustments (reduce when struggling, progressive overload when thriving).
All user-facing messages in German.
"""

import logging
from collections import defaultdict
from datetime import date, datetime, timedelta
from statistics import mean

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import (
    GoalAdjustment,
    KeyResult,
    Log,
    Routine,
    RoutineCompletion,
)

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

_COMPLIANCE_LOW = 0.40
_COMPLIANCE_HIGH = 0.95
_PROGRESSIVE_THRESHOLD = 0.90
_MIN_WEEKS_FOR_SUGGESTION = 3
_MIN_WEEKS_FOR_OVERLOAD = 2

# Expected completions per frequency within a week
_EXPECTED_PER_WEEK: dict[str, float] = {
    "daily": 7.0,
    "weekly": 1.0,
    "monthly": 0.25,  # ~1 per 4 weeks
    "once": 1.0,
}

# Progressive-overload step-up rules keyed by unit (lower-cased)
_STEP_UP_RULES: dict[str, tuple[float, str]] = {
    "l":        (0.5,  "+0.5 L"),
    "liter":    (0.5,  "+0.5 L"),
    "sessions": (1.0,  "+1 Einheit/Woche"),
    "einheiten":(1.0,  "+1 Einheit/Woche"),
    "steps":    (1000, "+1 000 Schritte"),
    "schritte": (1000, "+1 000 Schritte"),
    "wochen":   (1.0,  "+1 Woche"),
    "weeks":    (1.0,  "+1 Woche"),
}

# Default numeric step-up: 15 %
_DEFAULT_STEP_PERCENT = 0.15
# Default reduction factor
_REDUCTION_FACTOR = 0.80  # reduce by 20 %


# ── Helpers ───────────────────────────────────────────────────────────────────

def _week_bounds(ref: date, weeks_ago: int) -> tuple[datetime, datetime]:
    """Return (start, end) datetimes for *weeks_ago* full weeks before *ref*."""
    # Monday of the current week
    monday = ref - timedelta(days=ref.weekday())
    start = monday - timedelta(weeks=weeks_ago)
    end = start + timedelta(days=7)
    return datetime.combine(start, datetime.min.time()), datetime.combine(end, datetime.min.time())


def _determine_trend(rates: list[float]) -> str:
    if len(rates) < 2:
        return "stable"
    diffs = [rates[i + 1] - rates[i] for i in range(len(rates) - 1)]
    avg_diff = mean(diffs)
    if avg_diff > 0.05:
        return "improving"
    if avg_diff < -0.05:
        return "declining"
    return "stable"


def _step_up_value(current: float, unit: str | None) -> tuple[float, str]:
    """Compute the next progressive-overload target and a human label."""
    key = (unit or "").strip().lower()
    if key in _STEP_UP_RULES:
        increment, label = _STEP_UP_RULES[key]
        return round(current + increment, 2), label
    # Fallback: +15 %, rounded nicely
    new = round(current * (1 + _DEFAULT_STEP_PERCENT), 2)
    return new, f"+{_DEFAULT_STEP_PERCENT * 100:.0f} %"


def _reduce_value(current: float) -> float:
    return round(current * _REDUCTION_FACTOR, 2)


def _frequency_to_german(freq: str) -> str:
    mapping = {
        "daily": "Taeglich",
        "weekly": "Woechentlich",
        "monthly": "Monatlich",
        "3x_weekly": "3x pro Woche",
        "2x_weekly": "2x pro Woche",
    }
    return mapping.get(freq, freq)


# ── 1. KR Compliance Analysis ────────────────────────────────────────────────

async def analyze_kr_compliance(
    session: AsyncSession,
    user_id: int,
    key_result_id: int,
    weeks: int = 3,
) -> dict:
    """Analyse completion rate of a Key Result over the last *weeks* weeks."""
    kr = await session.get(KeyResult, key_result_id)
    if kr is None or kr.user_id != user_id:
        raise ValueError(f"KeyResult {key_result_id} nicht gefunden oder gehoert nicht zu User {user_id}.")

    today = date.today()
    expected_per_week = _EXPECTED_PER_WEEK.get(kr.frequency, 1.0)

    weekly_rates: list[float] = []
    for w in range(weeks, 0, -1):
        start_dt, end_dt = _week_bounds(today, w)
        stmt = (
            select(func.count())
            .select_from(Log)
            .where(
                and_(
                    Log.user_id == user_id,
                    Log.key_result_id == key_result_id,
                    Log.logged_at >= start_dt,
                    Log.logged_at < end_dt,
                )
            )
        )
        result = await session.execute(stmt)
        count = result.scalar() or 0
        rate = min(count / expected_per_week, 1.0) if expected_per_week > 0 else 0.0
        weekly_rates.append(round(rate, 4))

    compliance_rate = round(mean(weekly_rates), 4) if weekly_rates else 0.0
    trend = _determine_trend(weekly_rates)

    recommendation: str | None = None
    if compliance_rate < _COMPLIANCE_LOW:
        recommendation = (
            f"Deine Erfuellungsrate fuer '{kr.title}' liegt bei {compliance_rate * 100:.0f} %. "
            "Ueberlege, das Ziel zu reduzieren oder den Zeitplan anzupassen."
        )
    elif compliance_rate > _COMPLIANCE_HIGH:
        recommendation = (
            f"Starke Leistung bei '{kr.title}' ({compliance_rate * 100:.0f} %)! "
            "Zeit fuer eine Steigerung?"
        )

    return {
        "kr_id": kr.id,
        "kr_title": kr.title,
        "target_value": kr.target_value,
        "compliance_rate": compliance_rate,
        "weekly_rates": weekly_rates,
        "trend": trend,
        "recommendation": recommendation,
    }


# ── 2. Target Adjustment Suggestion ─────────────────────────────────────────

async def suggest_target_adjustment(
    session: AsyncSession,
    user_id: int,
    key_result_id: int,
) -> dict | None:
    """Suggest raising or lowering a KR target based on compliance history."""
    analysis = await analyze_kr_compliance(session, user_id, key_result_id, weeks=_MIN_WEEKS_FOR_SUGGESTION)
    rates = analysis["weekly_rates"]
    kr_title = analysis["kr_title"]
    target = analysis["target_value"]

    if target is None:
        return None

    # All weeks below threshold → suggest reduction
    if all(r < _COMPLIANCE_LOW for r in rates):
        new_target = _reduce_value(target)
        return {
            "kr_id": key_result_id,
            "kr_title": kr_title,
            "current_target": target,
            "suggested_target": new_target,
            "adjustment_type": "reduce",
            "reason": (
                f"Erfuellungsrate war {_MIN_WEEKS_FOR_SUGGESTION} Wochen in Folge unter "
                f"{_COMPLIANCE_LOW * 100:.0f} % (Schnitt {analysis['compliance_rate'] * 100:.0f} %). "
                f"Vorschlag: Ziel von {target} auf {new_target} senken."
            ),
            "confidence": round(1 - analysis["compliance_rate"], 2),
        }

    # All weeks above high threshold → suggest increase
    if all(r > _COMPLIANCE_HIGH for r in rates):
        new_target, label = _step_up_value(target, None)
        return {
            "kr_id": key_result_id,
            "kr_title": kr_title,
            "current_target": target,
            "suggested_target": new_target,
            "adjustment_type": "increase",
            "reason": (
                f"Erfuellungsrate war {_MIN_WEEKS_FOR_SUGGESTION} Wochen ueber "
                f"{_COMPLIANCE_HIGH * 100:.0f} % — progressive Steigerung ({label})."
            ),
            "confidence": round(analysis["compliance_rate"], 2),
        }

    return None


# ── 3. Routine Simplification ────────────────────────────────────────────────

async def suggest_routine_simplification(
    session: AsyncSession,
    user_id: int,
) -> list[dict]:
    """Find routines with low completion and suggest improvements."""
    stmt = select(Routine).where(
        and_(Routine.user_id == user_id, Routine.status == "active")
    )
    result = await session.execute(stmt)
    routines = result.scalars().all()

    today = date.today()
    lookback = datetime.combine(today - timedelta(weeks=_MIN_WEEKS_FOR_SUGGESTION), datetime.min.time())
    total_days = _MIN_WEEKS_FOR_SUGGESTION * 7

    suggestions: list[dict] = []

    for routine in routines:
        # Count completions in lookback window
        cnt_stmt = (
            select(func.count())
            .select_from(RoutineCompletion)
            .where(
                and_(
                    RoutineCompletion.routine_id == routine.id,
                    RoutineCompletion.user_id == user_id,
                    RoutineCompletion.completed_at >= lookback,
                )
            )
        )
        cnt_result = await session.execute(cnt_stmt)
        completions = cnt_result.scalar() or 0

        # Determine expected completions from frequency_human
        freq_lower = (routine.frequency_human or "").lower()
        if "taeglich" in freq_lower or "täglich" in freq_lower or "jeden tag" in freq_lower:
            expected = total_days
        elif "wöchentlich" in freq_lower or "woechentlich" in freq_lower or "jede woche" in freq_lower:
            expected = _MIN_WEEKS_FOR_SUGGESTION
        elif any(token in freq_lower for token in ["3x", "3 x", "dreimal"]):
            expected = _MIN_WEEKS_FOR_SUGGESTION * 3
        elif any(token in freq_lower for token in ["2x", "2 x", "zweimal"]):
            expected = _MIN_WEEKS_FOR_SUGGESTION * 2
        elif any(token in freq_lower for token in ["4x", "4 x", "viermal"]):
            expected = _MIN_WEEKS_FOR_SUGGESTION * 4
        elif any(token in freq_lower for token in ["5x", "5 x", "fuenfmal", "fünfmal"]):
            expected = _MIN_WEEKS_FOR_SUGGESTION * 5
        elif any(token in freq_lower for token in ["6x", "6 x", "sechsmal"]):
            expected = _MIN_WEEKS_FOR_SUGGESTION * 6
        else:
            # Fallback: treat as weekly
            expected = _MIN_WEEKS_FOR_SUGGESTION

        if expected <= 0:
            continue

        rate = min(completions / expected, 1.0)
        if rate >= _COMPLIANCE_LOW:
            continue

        tips: list[str] = []
        suggested_freq: str | None = None
        suggested_time: str | None = None

        # Suggest reduced frequency
        if expected >= total_days:
            tips.append("Reduziere von taeglich auf 3-4x pro Woche.")
            suggested_freq = "3x pro Woche"
        elif expected >= _MIN_WEEKS_FOR_SUGGESTION * 3:
            tips.append("Reduziere auf 2x pro Woche.")
            suggested_freq = "2x pro Woche"

        # Suggest different time of day
        current_time = routine.time_of_day or "anytime"
        if current_time == "morning":
            tips.append("Verschiebe auf den Abend — morgens scheint schwierig.")
            suggested_time = "evening"
        elif current_time == "evening":
            tips.append("Probiere es morgens — abends faellt es oft aus.")
            suggested_time = "morning"
        elif current_time == "anytime":
            tips.append("Lege eine feste Tageszeit fest fuer mehr Verbindlichkeit.")
            suggested_time = "morning"

        # Suggest shorter duration
        tips.append("Verkuerze die Dauer — lieber kurz und konsequent als lang und selten.")

        suggestions.append({
            "routine_id": routine.id,
            "routine_title": routine.title,
            "completion_rate": round(rate, 4),
            "suggestions": tips,
            "suggested_frequency": suggested_freq,
            "suggested_time_of_day": suggested_time,
        })

    return suggestions


# ── 4. Progressive Overload ──────────────────────────────────────────────────

async def apply_progressive_overload(
    session: AsyncSession,
    user_id: int,
) -> list[dict]:
    """For high-compliance KRs and routines, suggest stepping up."""
    results: list[dict] = []

    # ── KRs ───────────────────────────────────────────────────────────────
    kr_stmt = select(KeyResult).where(
        and_(KeyResult.user_id == user_id, KeyResult.status == "active")
    )
    kr_result = await session.execute(kr_stmt)
    key_results = kr_result.scalars().all()

    today = date.today()

    for kr in key_results:
        if kr.target_value is None:
            continue
        try:
            analysis = await analyze_kr_compliance(session, user_id, kr.id, weeks=_MIN_WEEKS_FOR_OVERLOAD)
        except ValueError:
            continue

        rates = analysis["weekly_rates"]
        if len(rates) < _MIN_WEEKS_FOR_OVERLOAD:
            continue
        if not all(r >= _PROGRESSIVE_THRESHOLD for r in rates):
            continue

        new_target, label = _step_up_value(kr.target_value, kr.unit)
        unit_display = kr.unit or ""
        results.append({
            "entity_type": "key_result",
            "entity_id": kr.id,
            "title": kr.title,
            "current_level": f"{kr.target_value} {unit_display}".strip(),
            "suggested_level": f"{new_target} {unit_display}".strip(),
            "message": (
                f"Du erreichst '{kr.title}' zuverlaessig ({analysis['compliance_rate'] * 100:.0f} %) "
                f"— erhoehe auf {new_target} {unit_display}?"
            ),
        })

    # ── Routines ──────────────────────────────────────────────────────────
    routine_stmt = select(Routine).where(
        and_(Routine.user_id == user_id, Routine.status == "active")
    )
    routine_result = await session.execute(routine_stmt)
    routines = routine_result.scalars().all()

    lookback = datetime.combine(today - timedelta(weeks=_MIN_WEEKS_FOR_OVERLOAD), datetime.min.time())
    total_days = _MIN_WEEKS_FOR_OVERLOAD * 7

    for routine in routines:
        freq_lower = (routine.frequency_human or "").lower()
        if "taeglich" in freq_lower or "täglich" in freq_lower or "jeden tag" in freq_lower:
            expected = total_days
        elif any(token in freq_lower for token in ["3x", "3 x", "dreimal"]):
            expected = _MIN_WEEKS_FOR_OVERLOAD * 3
        elif any(token in freq_lower for token in ["2x", "2 x", "zweimal"]):
            expected = _MIN_WEEKS_FOR_OVERLOAD * 2
        elif any(token in freq_lower for token in ["4x", "4 x", "viermal"]):
            expected = _MIN_WEEKS_FOR_OVERLOAD * 4
        elif any(token in freq_lower for token in ["5x", "5 x", "fuenfmal", "fünfmal"]):
            expected = _MIN_WEEKS_FOR_OVERLOAD * 5
        elif any(token in freq_lower for token in ["6x", "6 x", "sechsmal"]):
            expected = _MIN_WEEKS_FOR_OVERLOAD * 6
        else:
            expected = _MIN_WEEKS_FOR_OVERLOAD  # weekly fallback

        if expected <= 0:
            continue

        cnt_stmt = (
            select(func.count())
            .select_from(RoutineCompletion)
            .where(
                and_(
                    RoutineCompletion.routine_id == routine.id,
                    RoutineCompletion.user_id == user_id,
                    RoutineCompletion.completed_at >= lookback,
                )
            )
        )
        cnt_result = await session.execute(cnt_stmt)
        completions = cnt_result.scalar() or 0
        rate = min(completions / expected, 1.0)

        if rate < _PROGRESSIVE_THRESHOLD:
            continue

        # Suggest frequency increase
        current_freq = routine.frequency_human or "unbekannt"
        if "taeglich" in freq_lower or "täglich" in freq_lower:
            suggested = "Taeglich + laengere Dauer"
        elif any(token in freq_lower for token in ["5x", "6x"]):
            suggested = "Taeglich"
        elif any(token in freq_lower for token in ["3x", "4x"]):
            suggested = f"{current_freq} → +1x pro Woche"
        elif any(token in freq_lower for token in ["2x"]):
            suggested = "3x pro Woche"
        else:
            suggested = f"{current_freq} → +1x pro Woche"

        results.append({
            "entity_type": "routine",
            "entity_id": routine.id,
            "title": routine.title,
            "current_level": current_freq,
            "suggested_level": suggested,
            "message": (
                f"'{routine.title}' laeuft super ({rate * 100:.0f} % Abschlussrate) "
                f"— steigere auf {suggested}?"
            ),
        })

    return results


# ── 5. Full Adaptive Analysis ────────────────────────────────────────────────

async def run_adaptive_analysis(
    session: AsyncSession,
    user_id: int,
) -> dict:
    """Run all analyses, persist GoalAdjustment records, return summary."""
    reductions: list[dict] = []
    increases: list[dict] = []

    # Analyse every active KR
    kr_stmt = select(KeyResult).where(
        and_(KeyResult.user_id == user_id, KeyResult.status == "active")
    )
    kr_result = await session.execute(kr_stmt)
    key_results = kr_result.scalars().all()

    for kr in key_results:
        try:
            suggestion = await suggest_target_adjustment(session, user_id, kr.id)
        except Exception:
            logger.exception("Fehler bei KR-Analyse fuer KR %s", kr.id)
            continue
        if suggestion is None:
            continue

        adj = GoalAdjustment(
            user_id=user_id,
            entity_type="key_result",
            entity_id=kr.id,
            adjustment_type=suggestion["adjustment_type"],
            old_value=str(suggestion["current_target"]),
            new_value=str(suggestion["suggested_target"]),
            reason=suggestion["reason"],
            status="suggested",
        )
        session.add(adj)

        bucket = reductions if suggestion["adjustment_type"] == "reduce" else increases
        bucket.append(suggestion)

    # Routine simplification
    simplifications = await suggest_routine_simplification(session, user_id)
    for simp in simplifications:
        adj = GoalAdjustment(
            user_id=user_id,
            entity_type="routine",
            entity_id=simp["routine_id"],
            adjustment_type="simplify",
            old_value=None,
            new_value="; ".join(simp["suggestions"]),
            reason=f"Abschlussrate nur {simp['completion_rate'] * 100:.0f} %",
            status="suggested",
        )
        session.add(adj)

    # Progressive overload
    progressive_overloads = await apply_progressive_overload(session, user_id)
    for po in progressive_overloads:
        adj = GoalAdjustment(
            user_id=user_id,
            entity_type=po["entity_type"],
            entity_id=po["entity_id"],
            adjustment_type="progressive_overload",
            old_value=po["current_level"],
            new_value=po["suggested_level"],
            reason=po["message"],
            status="suggested",
        )
        session.add(adj)

    await session.flush()

    return {
        "reductions": reductions,
        "increases": increases,
        "simplifications": simplifications,
        "progressive_overloads": progressive_overloads,
    }


# ── 6. Accept Adjustment ─────────────────────────────────────────────────────

async def accept_adjustment(
    session: AsyncSession,
    adjustment_id: int,
) -> dict:
    """Apply a suggested adjustment and update the underlying entity."""
    adj = await session.get(GoalAdjustment, adjustment_id)
    if adj is None:
        raise ValueError(f"GoalAdjustment {adjustment_id} nicht gefunden.")
    if adj.status != "suggested":
        raise ValueError(f"Anpassung {adjustment_id} hat Status '{adj.status}' — nur 'suggested' kann akzeptiert werden.")

    adj.status = "accepted"

    if adj.entity_type == "key_result" and adj.adjustment_type in ("reduce", "increase", "progressive_overload"):
        kr = await session.get(KeyResult, adj.entity_id)
        if kr is not None and adj.new_value is not None:
            try:
                kr.target_value = float(adj.new_value)
            except ValueError:
                logger.warning("Konnte new_value '%s' nicht in float umwandeln fuer KR %s", adj.new_value, adj.entity_id)

    elif adj.entity_type == "routine" and adj.adjustment_type == "simplify":
        routine = await session.get(Routine, adj.entity_id)
        if routine is not None:
            # Apply suggested frequency if encoded
            if adj.new_value:
                parts = adj.new_value.split("; ")
                for part in parts:
                    lower = part.lower()
                    if "reduziere" in lower and "pro woche" in lower:
                        # Extract frequency suggestion
                        for token in ["3x pro Woche", "2x pro Woche", "4x pro Woche"]:
                            if token.lower() in lower or token in adj.new_value:
                                routine.frequency_human = token
                                break
                    if "verschiebe" in lower or "probiere" in lower or "feste tageszeit" in lower:
                        if "abend" in lower:
                            routine.time_of_day = "evening"
                        elif "morgen" in lower:
                            routine.time_of_day = "morning"

    elif adj.entity_type == "routine" and adj.adjustment_type == "progressive_overload":
        routine = await session.get(Routine, adj.entity_id)
        if routine is not None and adj.new_value:
            routine.frequency_human = adj.new_value

    await session.flush()

    return {
        "adjustment_id": adj.id,
        "status": "accepted",
        "entity_type": adj.entity_type,
        "entity_id": adj.entity_id,
        "message": f"Anpassung #{adj.id} wurde uebernommen.",
    }


# ── 7. Reject Adjustment ─────────────────────────────────────────────────────

async def reject_adjustment(
    session: AsyncSession,
    adjustment_id: int,
) -> dict:
    """Mark an adjustment as rejected without applying changes."""
    adj = await session.get(GoalAdjustment, adjustment_id)
    if adj is None:
        raise ValueError(f"GoalAdjustment {adjustment_id} nicht gefunden.")
    if adj.status != "suggested":
        raise ValueError(f"Anpassung {adjustment_id} hat Status '{adj.status}' — nur 'suggested' kann abgelehnt werden.")

    adj.status = "rejected"
    await session.flush()

    return {
        "adjustment_id": adj.id,
        "status": "rejected",
        "message": f"Anpassung #{adj.id} wurde abgelehnt.",
    }


# ── 8. Adaptive Summary for AI Prompt ────────────────────────────────────────

async def get_adaptive_summary(
    session: AsyncSession,
    user_id: int,
) -> str:
    """Return a context string listing pending adjustments for AI prompts."""
    stmt = (
        select(GoalAdjustment)
        .where(
            and_(
                GoalAdjustment.user_id == user_id,
                GoalAdjustment.status == "suggested",
            )
        )
        .order_by(GoalAdjustment.created_at.desc())
    )
    result = await session.execute(stmt)
    adjustments = result.scalars().all()

    if not adjustments:
        return "Keine ausstehenden Zielanpassungen."

    lines: list[str] = ["Ausstehende Zielanpassungen:"]
    for adj in adjustments:
        type_label = {
            "reduce": "Reduktion",
            "increase": "Steigerung",
            "simplify": "Vereinfachung",
            "progressive_overload": "Progressive Steigerung",
        }.get(adj.adjustment_type, adj.adjustment_type)

        entity_label = "KR" if adj.entity_type == "key_result" else "Routine"
        line = (
            f"- [{entity_label} #{adj.entity_id}] {type_label}: "
            f"{adj.old_value or '–'} → {adj.new_value or '–'} "
            f"(Grund: {adj.reason or 'k.A.'})"
        )
        lines.append(line)

    return "\n".join(lines)
