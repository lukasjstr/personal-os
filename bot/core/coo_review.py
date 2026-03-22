"""COO Sunday Strategic Review — weekly AI-driven life analysis and next week strategy.

This is the flagship intelligence feature: every Sunday evening the system synthesizes
all data from the past week across ALL life domains and delivers a personalized COO briefing:

1. Multi-domain performance summary (goals, health, finance, relationships, learning)
2. Pattern synthesis: what the data reveals that you haven't noticed
3. Correlation highlights: which behaviors impacted outcomes this week
4. Next-week strategy: specific, prioritized recommendations
5. Interactive — user can ask follow-up questions in the same session

Example output:
  📊 DEINE WOCHE — COO REVIEW

  Diese Woche: 3/5 Gesundheitsziele ✅, 4/4 Business-Ziele ✅

  🔍 WAS ICH BEOBACHTET HABE:
  • Du hast Workouts immer dann übersprungen, wenn du nach 22:30 Uhr geschlafen hast (3x)
  • An den 2 Tagen mit >2300mg Natrium warst du am Folgetag schlechter drauf
  • Deine Produktivität war Dienstag und Mittwoch am höchsten (beide Morgen-Routine ✅)

  🎯 EMPFEHLUNG FÜR NÄCHSTE WOCHE:
  • Priorisiere Schlaf vor 22:30 Uhr um Workouts zu sichern
  • Reduziere salzige Mahlzeiten am Vorabend von wichtigen Tagen
  • Plane deine Deep-Work-Blöcke für Dienstag/Mittwoch
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Optional

from openai import AsyncOpenAI
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import settings
from bot.database.models import (
    DailyContext,
    EveningCheckin,
    FinancialTransaction,
    FoodEntry,
    KeyResult,
    Log,
    Objective,
    RoutineCompletion,
    Task,
    User,
    WeeklyReflection,
)

logger = logging.getLogger(__name__)
openai_client = AsyncOpenAI(api_key=settings.openai_api_key)


async def generate_coo_weekly_review(
    session: AsyncSession,
    user: User,
    week_start: Optional[date] = None,
) -> str:
    """Generate the full COO Sunday Review message for Telegram."""
    today = date.today()
    week_start = week_start or (today - timedelta(days=today.weekday() + 1))  # Last Monday
    week_end = week_start + timedelta(days=6)

    # Gather all week data
    week_data = await _gather_week_data(session, user.id, week_start, week_end)

    # Build prompt with full context
    prompt = _build_review_prompt(user, week_data, week_start, week_end)

    response = await openai_client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": (
                    "Du bist der persönliche COO des Users. Deine Aufgabe ist es, "
                    "die Wochendaten zu analysieren und einen präzisen, personalisierten "
                    "strategischen Review zu liefern. Sei konkret, datenbasiert und proaktiv. "
                    "Nutze Markdown-Formatierung für Telegram. "
                    "Sprich den User direkt an (du/dein). Deutsch."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        max_tokens=1200,
        temperature=0.5,
    )

    review_text = response.choices[0].message.content or "Review konnte nicht generiert werden."

    # Save as WeeklyReflection
    try:
        reflection = WeeklyReflection(
            user_id=user.id,
            week_start=week_start,
            ai_summary=review_text,
            answers={},
        )
        session.add(reflection)
        await session.flush()
    except Exception as e:
        logger.warning("Could not save COO review as WeeklyReflection: %s", e)

    return review_text


async def _gather_week_data(
    session: AsyncSession,
    user_id: int,
    week_start: date,
    week_end: date,
) -> dict:
    """Gather all relevant data for the week."""
    ws_dt = datetime.combine(week_start, datetime.min.time())
    we_dt = datetime.combine(week_end, datetime.max.time())

    # Goals progress
    objectives = (await session.execute(
        select(Objective).where(and_(
            Objective.user_id == user_id,
            Objective.status == "active",
        ))
    )).scalars().all()

    key_results = (await session.execute(
        select(KeyResult).where(and_(
            KeyResult.user_id == user_id,
            KeyResult.status == "active",
        ))
    )).scalars().all()

    # Tasks completed this week
    tasks_done = (await session.execute(
        select(Task).where(and_(
            Task.user_id == user_id,
            Task.status == "done",
            Task.completed_at >= ws_dt,
            Task.completed_at <= we_dt,
        ))
    )).scalars().all()

    tasks_overdue = (await session.execute(
        select(func.count(Task.id)).where(and_(
            Task.user_id == user_id,
            Task.status.in_(["todo", "in_progress"]),
            Task.due_date < week_end,
        ))
    )).scalar() or 0

    # Routine completions
    routine_completions = (await session.execute(
        select(RoutineCompletion).where(and_(
            RoutineCompletion.user_id == user_id,
            RoutineCompletion.completed_at >= ws_dt,
            RoutineCompletion.completed_at <= we_dt,
        ))
    )).scalars().all()

    # Health metrics (logs)
    health_logs = (await session.execute(
        select(Log).where(and_(
            Log.user_id == user_id,
            Log.log_type.in_(["mood", "sleep", "water", "workout", "steps", "hrv"]),
            Log.logged_at >= ws_dt,
            Log.logged_at <= we_dt,
        ))
    )).scalars().all()

    # Nutrition
    food_entries = (await session.execute(
        select(FoodEntry).where(and_(
            FoodEntry.user_id == user_id,
            FoodEntry.logged_date >= week_start,
            FoodEntry.logged_date <= week_end,
        ))
    )).scalars().all()

    # Daily contexts (morning energy/focus)
    daily_contexts = (await session.execute(
        select(DailyContext).where(and_(
            DailyContext.user_id == user_id,
            DailyContext.date >= week_start,
            DailyContext.date <= week_end,
        ))
    )).scalars().all()

    # Evening check-ins
    evening_checkins = (await session.execute(
        select(EveningCheckin).where(and_(
            EveningCheckin.user_id == user_id,
            EveningCheckin.date >= week_start,
            EveningCheckin.date <= week_end,
        ))
    )).scalars().all()

    # Finance (this week)
    finance_logs = (await session.execute(
        select(FinancialTransaction).where(and_(
            FinancialTransaction.user_id == user_id,
            FinancialTransaction.transaction_date >= week_start,
            FinancialTransaction.transaction_date <= week_end,
        ))
    )).scalars().all()

    # Aggregate health metrics
    mood_scores = [float(l.data.get("score", 0)) for l in health_logs if l.log_type == "mood" and l.data.get("score")]
    sleep_hours = [float(l.data.get("hours", 0)) for l in health_logs if l.log_type == "sleep" and l.data.get("hours")]
    workout_days = len({l.logged_at.date() for l in health_logs if l.log_type == "workout"})
    water_by_day: dict[str, float] = {}
    for l in health_logs:
        if l.log_type == "water":
            d = l.logged_at.strftime("%Y-%m-%d")
            water_by_day[d] = water_by_day.get(d, 0) + float(l.data.get("amount", 0))

    # Aggregate nutrition
    total_sodium = sum(e.sodium_mg or 0 for e in food_entries)
    total_calories = sum(e.calories or 0 for e in food_entries)
    food_days_logged = len({e.logged_date for e in food_entries})
    high_sodium_days = []
    sodium_by_day: dict[str, float] = {}
    for e in food_entries:
        d = e.logged_date.isoformat()
        sodium_by_day[d] = sodium_by_day.get(d, 0) + (e.sodium_mg or 0)
    for d, v in sodium_by_day.items():
        if v > 2500:
            high_sodium_days.append((d, round(v)))

    # Finance totals
    total_expenses = sum(abs(t.amount) for t in finance_logs if t.transaction_type == "expense")
    total_income = sum(t.amount for t in finance_logs if t.transaction_type == "income")

    # Wins from evening check-ins
    wins = [c.win_text for c in evening_checkins if c.win_text]

    return {
        "objectives": objectives,
        "key_results": key_results,
        "tasks_done": len(tasks_done),
        "tasks_overdue": tasks_overdue,
        "task_titles_done": [t.title for t in tasks_done[:8]],
        "routine_completions": len(routine_completions),
        "mood_avg": round(sum(mood_scores) / len(mood_scores), 1) if mood_scores else None,
        "mood_min": round(min(mood_scores), 1) if mood_scores else None,
        "mood_max": round(max(mood_scores), 1) if mood_scores else None,
        "sleep_avg": round(sum(sleep_hours) / len(sleep_hours), 1) if sleep_hours else None,
        "workout_days": workout_days,
        "water_avg": round(sum(water_by_day.values()) / len(water_by_day), 1) if water_by_day else None,
        "food_days_logged": food_days_logged,
        "total_calories_week": round(total_calories) if total_calories else None,
        "high_sodium_days": high_sodium_days,
        "energy_ratings": [float(c.energy) for c in daily_contexts if c.energy],
        "wins": wins[:5],
        "total_expenses": round(total_expenses, 2) if total_expenses else None,
        "total_income": round(total_income, 2) if total_income else None,
        "days_with_data": len(daily_contexts),
    }


def _build_review_prompt(user: User, data: dict, week_start: date, week_end: date) -> str:
    """Build the full prompt for GPT-4o to generate the COO review."""
    name = user.first_name or "du"
    week_str = f"{week_start.strftime('%d.%m.')}–{week_end.strftime('%d.%m.%Y')}"

    # Goals section
    goals_text = ""
    if data["objectives"]:
        krs = data["key_results"]
        krs_by_obj: dict[int, list] = {}
        for kr in krs:
            krs_by_obj.setdefault(kr.objective_id, []).append(kr)

        for obj in data["objectives"][:5]:
            obj_krs = krs_by_obj.get(obj.id, [])
            if obj_krs:
                kr_summary = ", ".join(
                    f"{kr.title}: {int(kr.current_value or 0)}/{int(kr.target_value or 0)}"
                    for kr in obj_krs[:3]
                )
                goals_text += f"  • {obj.title} [{obj.category}]: {kr_summary}\n"
            else:
                goals_text += f"  • {obj.title} [{obj.category}]: Keine KRs\n"

    # Health section
    health_parts = []
    if data["mood_avg"]:
        health_parts.append(f"Mood Ø {data['mood_avg']}/10 (min {data['mood_min']}, max {data['mood_max']})")
    if data["sleep_avg"]:
        health_parts.append(f"Schlaf Ø {data['sleep_avg']}h")
    if data["workout_days"]:
        health_parts.append(f"{data['workout_days']} Trainingstage")
    if data["water_avg"]:
        health_parts.append(f"Wasser Ø {data['water_avg']}L")
    if data["high_sodium_days"]:
        health_parts.append(f"Hohe Natriumtage: {', '.join(f'{d} ({mg}mg)' for d, mg in data['high_sodium_days'])}")

    # Wins
    wins_text = "\n".join(f"  • {w}" for w in data["wins"]) if data["wins"] else "  • Keine Wins eingetragen"

    # Finance
    finance_text = ""
    if data["total_expenses"]:
        finance_text = f"Ausgaben diese Woche: {data['total_expenses']}€"
    if data["total_income"]:
        finance_text += f", Einnahmen: {data['total_income']}€"

    prompt = f"""Analysiere die folgende Woche für {name} ({week_str}) und erstelle einen COO-Review.

## WOCHENDATEN

**Ziele & Key Results:**
{goals_text or '  Keine aktiven Ziele'}

**Tasks:** {data['tasks_done']} erledigt, {data['tasks_overdue']} überfällig
**Erledigte Tasks:** {', '.join(data['task_titles_done']) or 'Keine'}

**Routinen:** {data['routine_completions']} Completions diese Woche

**Gesundheit:**
{chr(10).join(f'  • {p}' for p in health_parts) if health_parts else '  Keine Gesundheitsdaten'}

**Ernährung:** {data['food_days_logged']} Tage geloggt{f', gesamt ca. {data["total_calories_week"]} kcal' if data.get('total_calories_week') else ''}

**Energie-Ratings (1-10):** {data['energy_ratings'] or 'Keine Daten'}

**Wins der Woche:**
{wins_text}

{'**Finanzen:** ' + finance_text if finance_text else ''}

## AUFGABE

Erstelle jetzt den COO Sunday Review mit:

1. **📊 DEINE WOCHE** — Kurze Zusammenfassung (3-4 Sätze, konkrete Zahlen)

2. **🔍 WAS ICH BEOBACHTET HABE** — 3-5 datenbasierte Beobachtungen/Muster:
   - Korrelationen (z.B. hohe Natriumtage vs. nächste-Tag-Energie)
   - Verhaltenmuster (wann wurden Routinen übersprungen?)
   - Überraschende Erkenntnisse

3. **🎯 STRATEGIE FÜR NÄCHSTE WOCHE** — 3 konkrete, priorisierte Empfehlungen
   - Jede Empfehlung mit Begründung aus den Daten
   - Actionable, nicht generisch

4. **💡 EINE SACHE** — Die EINE wichtigste Maßnahme für maximalen Impact

Sei direkt, datenbasiert, konkret. Kein Blabla. Max. 600 Wörter."""

    return prompt
