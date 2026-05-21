"""V3 P11 — Quarterly Review kalibriert auf 9 Lebensbereiche.

Scoring per area (0-100):
    obj_score   = avg KR completion ratio (0-1)
    consistency = weeks with ≥1 log / 13
    final       = 0.7 * obj_score + 0.3 * consistency
    area_score  = mean(final_per_objective) * 100

Aggregate life_score = mean(area_score) across areas with active objectives.

AI analysis (GPT-4o) injects Bedrock + scores + previous quarter and asks for
STÄRKEN / SCHWÄCHEN / PATTERN / KILLER-QUESTION + suggested next quarter.
"""
from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta
from typing import Optional

from openai import AsyncOpenAI
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from bot.config import settings
from bot.database.models import (
    KeyResult, LifeArea, LifeProfile, Log, Objective, QuarterlyReview, User,
)

logger = logging.getLogger(__name__)
openai_client = AsyncOpenAI(api_key=settings.openai_api_key)


# ─── Quarter helpers ──────────────────────────────────────────────────────────


def _get_current_quarter(ref_date: Optional[date] = None) -> tuple[int, int]:
    d = ref_date or date.today()
    return d.year, (d.month - 1) // 3 + 1


def _get_previous_quarter(ref_date: Optional[date] = None) -> tuple[int, int]:
    d = ref_date or date.today()
    q = (d.month - 1) // 3 + 1
    if q == 1:
        return d.year - 1, 4
    return d.year, q - 1


def _quarter_bounds(year: int, quarter: int) -> tuple[date, date]:
    start = date(year, (quarter - 1) * 3 + 1, 1)
    end_month = quarter * 3
    end_day = 31 if end_month in (3, 12) else 30
    return start, date(year, end_month, end_day)


# ─── Scoring ──────────────────────────────────────────────────────────────────


def grade_objective(obj: Objective, krs: list[KeyResult]) -> float:
    if not krs:
        return 0.0
    ratios: list[float] = []
    for kr in krs:
        if kr.status == "completed":
            ratios.append(1.0)
        elif kr.target_value and kr.target_value > 0:
            ratios.append(min(1.0, (kr.current_value or 0) / kr.target_value))
        else:
            ratios.append(0.0)
    return sum(ratios) / len(ratios)


async def _consistency_for_objective(
    session: AsyncSession, obj_id: int, q_start: date, q_end: date
) -> float:
    """Return fraction of quarter weeks that had ≥1 log on any KR of this objective."""
    start_dt = datetime.combine(q_start, datetime.min.time())
    end_dt = datetime.combine(q_end, datetime.max.time())
    logs = (await session.execute(
        select(Log.logged_at)
        .join(KeyResult, Log.key_result_id == KeyResult.id)
        .where(and_(
            KeyResult.objective_id == obj_id,
            Log.logged_at >= start_dt,
            Log.logged_at <= end_dt,
        ))
    )).scalars().all()
    if not logs:
        return 0.0
    weeks = {(d.isocalendar().week, d.isocalendar().year) for d in logs}
    return min(1.0, len(weeks) / 13.0)


async def calculate_life_area_score(
    session: AsyncSession, user_id: int, life_area_id: int,
    q_start: date, q_end: date,
) -> int:
    """0-100 score for one life area over the quarter."""
    objs = (await session.execute(
        select(Objective).options(selectinload(Objective.key_results)).where(and_(
            Objective.user_id == user_id,
            Objective.life_area_id == life_area_id,
            Objective.status.in_(["active", "completed"]),
        ))
    )).scalars().all()
    if not objs:
        return 0

    accumulated = 0.0
    counted = 0
    for obj in objs:
        active_krs = [kr for kr in obj.key_results if kr.status in ("active", "completed")]
        obj_score = grade_objective(obj, active_krs)
        consistency = await _consistency_for_objective(session, obj.id, q_start, q_end)
        final = (obj_score * 0.7) + (consistency * 0.3)
        accumulated += final
        counted += 1
    return int((accumulated / counted) * 100) if counted else 0


def calculate_life_score(area_scores: dict[str, int]) -> int:
    """Aggregated Life Score = unweighted mean across areas with active objectives."""
    nonzero = [v for v in area_scores.values() if v > 0]
    return int(sum(nonzero) / len(nonzero)) if nonzero else 0


# ─── Main entrypoint ──────────────────────────────────────────────────────────


async def generate_quarterly_review(
    session: AsyncSession,
    user_id: int,
    year: Optional[int] = None,
    quarter: Optional[int] = None,
    *,
    auto_close: bool = False,
) -> QuarterlyReview:
    """Compute scores + AI analysis for one user/quarter. Upserts QuarterlyReview.

    If `auto_close=False` (default for new V3 P11 flow), `completed_at` stays
    NULL and the user must run `/confirm_q` to sign off.
    """
    if year is None or quarter is None:
        py, pq = _get_previous_quarter()
        year = year or py
        quarter = quarter or pq

    quarter_label = f"Q{quarter} {year}"
    q_start, q_end = _quarter_bounds(year, quarter)

    user = (await session.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None:
        raise ValueError(f"User {user_id} not found")

    # Per-area scores
    areas = (await session.execute(
        select(LifeArea).where(LifeArea.user_id == user_id)
        .order_by(LifeArea.priority.asc())
    )).scalars().all()
    area_scores: dict[str, int] = {}
    for area in areas:
        area_scores[area.short_code] = await calculate_life_area_score(
            session, user_id, area.id, q_start, q_end,
        )
    life_score = calculate_life_score(area_scores)

    # Objectives data (for the dashboard + AI prompt)
    objs = (await session.execute(
        select(Objective).options(selectinload(Objective.key_results)).where(and_(
            Objective.user_id == user_id,
            Objective.status.in_(["active", "completed"]),
        )).order_by(Objective.priority_weight.desc())
    )).scalars().all()
    objectives_data: list[dict] = []
    for obj in objs:
        active_krs = [kr for kr in obj.key_results if kr.status in ("active", "completed")]
        grade = grade_objective(obj, active_krs)
        consistency = await _consistency_for_objective(session, obj.id, q_start, q_end)
        objectives_data.append({
            "id": obj.id,
            "title": obj.title,
            "category": obj.category,
            "life_area_id": obj.life_area_id,
            "status": obj.status,
            "grade": round(grade, 3),
            "grade_pct": round(grade * 100),
            "consistency": round(consistency, 2),
            "kr_count": len(active_krs),
        })

    # Previous quarter for trend
    py, pq = ((year - 1, 4) if quarter == 1 else (year, quarter - 1))
    previous = (await session.execute(
        select(QuarterlyReview).where(and_(
            QuarterlyReview.user_id == user_id,
            QuarterlyReview.year == py,
            QuarterlyReview.quarter == pq,
        ))
    )).scalar_one_or_none()
    previous_life_score = previous.life_score if previous else None
    previous_area_scores = (previous.life_area_scores or {}) if previous else {}

    # AI analysis with Bedrock
    ai_analysis, highlights, challenges, suggested_next = await _generate_v3_ai_analysis(
        session, user_id, quarter_label, area_scores, previous_area_scores,
        objectives_data, life_score,
    )

    # Upsert
    review = (await session.execute(
        select(QuarterlyReview).where(and_(
            QuarterlyReview.user_id == user_id,
            QuarterlyReview.year == year,
            QuarterlyReview.quarter == quarter,
        ))
    )).scalar_one_or_none()

    completed_ts = datetime.utcnow() if auto_close else None

    if review:
        review.quarter_label = quarter_label
        review.life_score = life_score
        review.life_area_scores = area_scores
        review.previous_life_score = previous_life_score
        review.objectives_data = objectives_data
        review.ai_analysis = ai_analysis
        review.highlights = highlights
        review.challenges = challenges
        review.suggested_next_quarter = suggested_next
        review.status = "completed" if auto_close else "pending_confirm"
        review.completed_at = completed_ts
        review.generated_at = datetime.utcnow()
    else:
        review = QuarterlyReview(
            user_id=user_id,
            year=year,
            quarter=quarter,
            quarter_label=quarter_label,
            life_score=life_score,
            life_area_scores=area_scores,
            previous_life_score=previous_life_score,
            objectives_data=objectives_data,
            ai_analysis=ai_analysis,
            highlights=highlights,
            challenges=challenges,
            suggested_next_quarter=suggested_next,
            status="completed" if auto_close else "pending_confirm",
            completed_at=completed_ts,
        )
        session.add(review)

    await session.flush()
    return review


async def confirm_quarterly_review(
    session: AsyncSession, user_id: int, review_id: int, user_reflection: Optional[str] = None,
) -> Optional[QuarterlyReview]:
    """Sign off on a quarterly review (sets completed_at + optional reflection)."""
    review = (await session.execute(
        select(QuarterlyReview).where(and_(
            QuarterlyReview.id == review_id,
            QuarterlyReview.user_id == user_id,
        ))
    )).scalar_one_or_none()
    if review is None:
        return None
    review.completed_at = datetime.utcnow()
    review.status = "completed"
    if user_reflection:
        review.user_reflection = user_reflection
    await session.flush()
    return review


# ─── AI analysis ──────────────────────────────────────────────────────────────


ANALYSIS_SYSTEM = (
    "Du bist Coach für Lukas. Analysiere ehrlich. KEIN Lob für Selbstverständlichkeiten. "
    "KEIN Trostpflaster für niedrige Scores. Coach-Modus aus dem System Prompt gilt."
)


async def _generate_v3_ai_analysis(
    session: AsyncSession,
    user_id: int,
    quarter_label: str,
    area_scores: dict[str, int],
    previous_area_scores: dict[str, int],
    objectives_data: list[dict],
    life_score: int,
) -> tuple[str, list[str], list[str], dict]:
    """Returns (analysis, highlights, challenges, suggested_next_quarter)."""
    # Bedrock
    profile = (await session.execute(
        select(LifeProfile).where(LifeProfile.user_id == user_id)
    )).scalar_one_or_none()
    bedrock_summary = ""
    if profile and profile.bedrock:
        b = profile.bedrock
        bedrock_summary = (
            f"Leitspruch: {b.get('leitspruch', '')[:200]}\n"
            f"Bottleneck: {b.get('bottleneck', '')}\n"
            f"Schwächen: {', '.join(b.get('weaknesses') or [])}\n"
        )

    area_lines = "\n".join(
        f"  - {code}: {score}/100"
        + (f"  (Q-1: {previous_area_scores[code]})" if code in previous_area_scores else "")
        for code, score in sorted(area_scores.items(), key=lambda kv: -kv[1])
    )
    obj_summary = "\n".join(
        f"  - {o['title']} [{o['category']}]: {o['grade_pct']}% (consistency {int(o['consistency']*100)}%)"
        for o in objectives_data[:12]
    )

    user_prompt = f"""Quartal: {quarter_label}
Aggregierter Life Score: {life_score}/100

Lebensbereich-Scores:
{area_lines}

Aktive Objectives (max 12):
{obj_summary}

Lukas's Bedrock:
{bedrock_summary}

Antworte mit JSON (max 250 Wörter pro Feld, ohne Markdown):
{{
  "analysis": "STÄRKEN: 2-3 Sätze. SCHWÄCHEN: 2-3 Sätze (konkret, nicht weichgespült). PATTERN: Was wiederholt sich? KILLER-QUESTION: 1 Frage die Lukas vor Q+1 beantworten MUSS.",
  "highlights": ["Highlight 1", "Highlight 2", "Highlight 3"],
  "challenges": ["Challenge 1", "Challenge 2", "Challenge 3"],
  "suggested_next_quarter": {{
    "focus_areas": ["area_short_code", ...],
    "actions": ["3 konkrete Vorschläge"]
  }}
}}"""

    try:
        resp = await openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": ANALYSIS_SYSTEM},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            max_tokens=1200,
            temperature=0.6,
        )
        data = json.loads(resp.choices[0].message.content or "{}")
        raw_analysis = data.get("analysis")
        if isinstance(raw_analysis, dict):
            # AI sometimes returns a structured dict — flatten to readable text
            analysis = "\n\n".join(
                f"{k}: {v}" for k, v in raw_analysis.items() if v
            )
        elif raw_analysis is None:
            analysis = "Keine Analyse verfügbar."
        else:
            analysis = str(raw_analysis)
        return (
            analysis,
            data.get("highlights", []) or [],
            data.get("challenges", []) or [],
            data.get("suggested_next_quarter", {}) or {},
        )
    except Exception:
        logger.exception("V3 quarterly AI analysis failed")
        return (
            f"Life Score: {life_score}/100. AI-Analyse temporär nicht verfügbar.",
            [], [], {},
        )


# ─── Context helper (kept for legacy callers) ────────────────────────────────


async def get_quarterly_context(session: AsyncSession, user_id: int) -> str:
    review = (await session.execute(
        select(QuarterlyReview)
        .where(QuarterlyReview.user_id == user_id)
        .order_by(QuarterlyReview.generated_at.desc())
        .limit(1)
    )).scalar_one_or_none()
    if not review:
        return ""
    lines = [f"=== LETZTER QUARTALS-REVIEW ({review.quarter_label}) ==="]
    lines.append(f"Life Score: {review.life_score}/100")
    if review.life_area_scores:
        top = sorted(review.life_area_scores.items(), key=lambda kv: -kv[1])[:3]
        lines.append("Top-Bereiche: " + ", ".join(f"{k} {v}" for k, v in top))
    if review.highlights:
        lines.append("Highlights: " + ", ".join(review.highlights[:3]))
    if review.challenges:
        lines.append("Challenges: " + ", ".join(review.challenges[:3]))
    lines.append("")
    return "\n".join(lines)


async def format_quarterly_review_for_telegram(review: QuarterlyReview) -> str:
    """Render a QuarterlyReview as Coach-Modus Telegram message."""
    lines: list[str] = []
    trend = ""
    if review.previous_life_score is not None:
        diff = (review.life_score or 0) - review.previous_life_score
        sign = "+" if diff >= 0 else ""
        trend = f"  (Q-1: {review.previous_life_score} → {sign}{diff})"
    lines.append(f"━━ {review.quarter_label} — LIFE SCORE: {review.life_score}/100 ━━{trend}")
    lines.append("")
    if review.life_area_scores:
        lines.append("Lebensbereiche:")
        for code, score in sorted(review.life_area_scores.items(), key=lambda kv: -kv[1]):
            bar = "█" * (score // 10) + "░" * (10 - score // 10)
            lines.append(f"  {code:<13s} {score:>3d} {bar}")
        lines.append("")
    if review.ai_analysis:
        lines.append("AI-Analyse:")
        lines.append(review.ai_analysis)
        lines.append("")
    snq = review.suggested_next_quarter or {}
    if snq.get("actions"):
        lines.append("Vorschläge nächstes Quartal:")
        for a in snq["actions"][:5]:
            lines.append(f"  · {a}")
        lines.append("")
    if review.completed_at is None:
        lines.append("Reply mit eigener Reflexion oder /confirm_q zum Abschließen.")
    else:
        lines.append(f"Abgeschlossen: {review.completed_at.strftime('%d.%m.%Y %H:%M')}")
    return "\n".join(lines)
