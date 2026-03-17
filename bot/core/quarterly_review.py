"""Feature 6: Quarterly Review — generate graded OKR review with AI analysis."""
import logging
from datetime import datetime, date
from typing import Optional

from openai import AsyncOpenAI
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from bot.config import settings
from bot.database.models import KeyResult, Objective, QuarterlyReview, User

logger = logging.getLogger(__name__)
openai_client = AsyncOpenAI(api_key=settings.openai_api_key)


def _get_current_quarter(ref_date: Optional[date] = None) -> tuple[int, int]:
    """Return (year, quarter) for today."""
    d = ref_date or date.today()
    q = (d.month - 1) // 3 + 1
    return d.year, q


def _get_previous_quarter(ref_date: Optional[date] = None) -> tuple[int, int]:
    """Return (year, quarter) for the previous quarter."""
    d = ref_date or date.today()
    q = (d.month - 1) // 3 + 1
    if q == 1:
        return d.year - 1, 4
    return d.year, q - 1


def grade_objective(obj: Objective, krs: list[KeyResult]) -> float:
    """Return average KR completion ratio (0.0–1.0)."""
    if not krs:
        return 0.0
    ratios = []
    for kr in krs:
        if kr.status == "completed":
            ratios.append(1.0)
        elif kr.target_value and kr.target_value > 0:
            ratio = min(1.0, (kr.current_value or 0) / kr.target_value)
            ratios.append(ratio)
        else:
            # boolean / streak — treat active as 0, completed as 1
            ratios.append(0.0)
    return sum(ratios) / len(ratios)


async def generate_quarterly_review(
    session: AsyncSession,
    user_id: int,
    year: Optional[int] = None,
    quarter: Optional[int] = None,
) -> QuarterlyReview:
    """Generate a quarterly review.

    Defaults to the previous quarter unless explicitly overridden.
    Upserts the QuarterlyReview row (regenerates if already exists).
    """
    if year is None or quarter is None:
        py, pq = _get_previous_quarter()
        year = year or py
        quarter = quarter or pq

    quarter_label = f"Q{quarter} {year}"

    # Load user
    user_result = await session.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one_or_none()
    if not user:
        raise ValueError(f"User {user_id} not found")

    # Load objectives (active + completed within this quarter)
    quarter_start = date(year, (quarter - 1) * 3 + 1, 1)
    quarter_end_month = quarter * 3
    quarter_end_day = 31 if quarter_end_month in (3, 12) else 30
    quarter_end = date(year, quarter_end_month, quarter_end_day)

    obj_result = await session.execute(
        select(Objective)
        .options(selectinload(Objective.key_results))
        .where(
            and_(
                Objective.user_id == user_id,
                Objective.status.in_(["active", "completed"]),
            )
        )
        .order_by(Objective.priority_weight.desc())
    )
    objectives = obj_result.scalars().all()

    # Grade each objective
    objectives_data = []
    total_score = 0.0
    graded_count = 0

    for obj in objectives:
        active_krs = [kr for kr in obj.key_results if kr.status in ("active", "completed")]
        grade = grade_objective(obj, active_krs)
        objectives_data.append({
            "id": obj.id,
            "title": obj.title,
            "category": obj.category,
            "status": obj.status,
            "grade": round(grade, 3),
            "grade_pct": round(grade * 100),
            "kr_count": len(active_krs),
            "krs": [
                {
                    "id": kr.id,
                    "title": kr.title,
                    "current_value": kr.current_value,
                    "target_value": kr.target_value,
                    "status": kr.status,
                }
                for kr in active_krs
            ],
        })
        total_score += grade
        graded_count += 1

    # Life score: weighted average across categories (0–100)
    if graded_count > 0:
        raw_life_score = (total_score / graded_count) * 100
        life_score = round(raw_life_score)
    else:
        life_score = 0

    # AI analysis
    ai_analysis, highlights, challenges = await _generate_ai_analysis(
        user, quarter_label, objectives_data, life_score
    )

    # Upsert
    existing = await session.execute(
        select(QuarterlyReview).where(
            and_(
                QuarterlyReview.user_id == user_id,
                QuarterlyReview.year == year,
                QuarterlyReview.quarter == quarter,
            )
        )
    )
    review = existing.scalar_one_or_none()

    if review:
        review.quarter_label = quarter_label
        review.life_score = life_score
        review.objectives_data = objectives_data
        review.ai_analysis = ai_analysis
        review.highlights = highlights
        review.challenges = challenges
        review.status = "completed"
        review.generated_at = datetime.utcnow()
    else:
        review = QuarterlyReview(
            user_id=user_id,
            year=year,
            quarter=quarter,
            quarter_label=quarter_label,
            life_score=life_score,
            objectives_data=objectives_data,
            ai_analysis=ai_analysis,
            highlights=highlights,
            challenges=challenges,
            status="completed",
        )
        session.add(review)

    await session.flush()
    return review


async def _generate_ai_analysis(
    user: User,
    quarter_label: str,
    objectives_data: list[dict],
    life_score: int,
) -> tuple[str, list[str], list[str]]:
    """Call GPT-4o to generate quarter analysis, highlights, and challenges."""
    try:
        obj_summary = "\n".join(
            f"- [{o['category'].upper()}] {o['title']}: {o['grade_pct']}% ({o['kr_count']} KRs)"
            for o in objectives_data
        )

        prompt = f"""Du bist ein persönlicher Life-Coach und analysierst den Quartals-Review für {quarter_label}.

Life Score: {life_score}/100

Objectives und Ergebnisse:
{obj_summary}

Erstelle eine ehrliche, motivierende Analyse auf Deutsch. Antworte im folgenden JSON-Format:
{{
  "analysis": "2-3 Absätze Gesamtanalyse",
  "highlights": ["Highlight 1", "Highlight 2", "Highlight 3"],
  "challenges": ["Challenge 1", "Challenge 2", "Challenge 3"]
}}"""

        resp = await openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            max_tokens=800,
            temperature=0.7,
        )

        import json
        data = json.loads(resp.choices[0].message.content or "{}")
        analysis = data.get("analysis", "Keine Analyse verfügbar.")
        highlights = data.get("highlights", [])
        challenges = data.get("challenges", [])
        return analysis, highlights, challenges

    except Exception:
        logger.exception("Failed to generate quarterly AI analysis")
        return (
            f"Life Score für {quarter_label}: {life_score}/100. Analyse konnte nicht generiert werden.",
            [],
            [],
        )


async def get_quarterly_context(session: AsyncSession, user_id: int) -> str:
    """Return the most recent quarterly review summary for AI context."""
    result = await session.execute(
        select(QuarterlyReview)
        .where(QuarterlyReview.user_id == user_id)
        .order_by(QuarterlyReview.generated_at.desc())
        .limit(1)
    )
    review = result.scalar_one_or_none()
    if not review:
        return ""

    lines = [f"=== LETZTER QUARTALS-REVIEW ({review.quarter_label}) ==="]
    lines.append(f"Life Score: {review.life_score}/100")
    if review.highlights:
        lines.append("Highlights: " + ", ".join(review.highlights[:3]))
    if review.challenges:
        lines.append("Herausforderungen: " + ", ".join(review.challenges[:3]))
    lines.append("")
    return "\n".join(lines)
