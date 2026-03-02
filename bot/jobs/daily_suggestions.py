"""Phase 8.2: Daily AI suggestions — runs at 06:30 before the morning brief."""
import json
import logging
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from openai import AsyncOpenAI
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import settings
from bot.database.connection import get_session
from bot.database.models import (
    DailySuggestion, KeyResult, Log, Objective, RoutineCompletion,
    User, WeeklyPriority, WeeklyReflection,
)

logger = logging.getLogger(__name__)
openai_client = AsyncOpenAI(api_key=settings.openai_api_key)

_JOB_HOUR = 6
_JOB_MINUTE = 30


async def generate_daily_suggestions() -> None:
    """Run at 06:30 Berlin time. Generate AI suggestions for every active user."""
    now_berlin = datetime.now(tz=ZoneInfo("Europe/Berlin"))
    if now_berlin.hour != _JOB_HOUR or now_berlin.minute != _JOB_MINUTE:
        return

    today = now_berlin.date()

    async with get_session() as session:
        result = await session.execute(
            select(User).where(User.is_active == True)  # noqa: E712
        )
        users = result.scalars().all()

        for user in users:
            try:
                await _generate_for_user(session, user, today)
            except Exception:
                logger.exception("Failed to generate daily suggestions for user %s", user.id)


async def _generate_for_user(session: AsyncSession, user: User, today: date) -> DailySuggestion | None:
    """Generate (or skip if already exists) suggestions for a single user."""
    existing = await session.execute(
        select(DailySuggestion).where(and_(
            DailySuggestion.user_id == user.id,
            DailySuggestion.date == today,
        ))
    )
    if existing.scalar_one_or_none():
        return None

    context = await _build_context(session, user, today)
    suggestions = await _call_gpt(user, today, context)

    suggestion = DailySuggestion(
        user_id=user.id,
        date=today,
        suggestions=suggestions,
    )
    session.add(suggestion)
    await session.flush()
    logger.info("Daily suggestions generated for user %s", user.id)
    return suggestion


async def _build_context(session: AsyncSession, user: User, today: date) -> dict:
    """Fetch all relevant user data for the GPT context."""
    seven_days_ago = datetime.combine(today - timedelta(days=7), datetime.min.time())
    today_dt = datetime.combine(today, datetime.min.time())

    # Active objectives + key results
    obj_result = await session.execute(
        select(Objective).where(and_(
            Objective.user_id == user.id,
            Objective.status == "active",
        ))
    )
    objectives = obj_result.scalars().all()

    obj_ids = [o.id for o in objectives]
    kr_result = await session.execute(
        select(KeyResult).where(and_(
            KeyResult.user_id == user.id,
            KeyResult.status == "active",
            KeyResult.objective_id.in_(obj_ids) if obj_ids else KeyResult.id == -1,
        ))
    )
    key_results = kr_result.scalars().all()

    # Last 7 days logs
    logs_result = await session.execute(
        select(Log).where(and_(
            Log.user_id == user.id,
            Log.logged_at >= seven_days_ago,
        )).order_by(Log.logged_at.desc()).limit(50)
    )
    recent_logs = logs_result.scalars().all()

    # Latest mood
    mood_result = await session.execute(
        select(Log).where(and_(
            Log.user_id == user.id,
            Log.log_type == "mood",
        )).order_by(Log.logged_at.desc()).limit(1)
    )
    latest_mood = mood_result.scalar_one_or_none()

    # Streak: count consecutive days with at least one log
    streak = _compute_streak(recent_logs, today)

    # Last weekly reflection
    refl_result = await session.execute(
        select(WeeklyReflection).where(and_(
            WeeklyReflection.user_id == user.id,
            WeeklyReflection.status == "completed",
        )).order_by(WeeklyReflection.week_start.desc()).limit(1)
    )
    last_reflection = refl_result.scalar_one_or_none()

    # Current week priorities (dimension focus)
    week_start = today - timedelta(days=today.weekday())
    wp_result = await session.execute(
        select(WeeklyPriority).where(and_(
            WeeklyPriority.user_id == user.id,
            WeeklyPriority.week_start == week_start,
        )).order_by(WeeklyPriority.priority_rank)
    )
    weekly_priorities = wp_result.scalars().all()

    # Routine streak: check last 3 days completion
    rc_result = await session.execute(
        select(RoutineCompletion).where(and_(
            RoutineCompletion.user_id == user.id,
            RoutineCompletion.completed_at >= seven_days_ago,
        ))
    )
    routine_completions = rc_result.scalars().all()
    routine_days = {rc.completed_at.date() for rc in routine_completions}
    routine_streak = 0
    check_day = today - timedelta(days=1)
    while check_day in routine_days:
        routine_streak += 1
        check_day -= timedelta(days=1)

    return {
        "objectives": objectives,
        "key_results": key_results,
        "recent_logs": recent_logs,
        "latest_mood": latest_mood,
        "streak": streak,
        "routine_streak": routine_streak,
        "last_reflection": last_reflection,
        "weekly_priorities": weekly_priorities,
    }


def _compute_streak(logs: list[Log], today: date) -> int:
    log_days = {log.logged_at.date() for log in logs}
    streak = 0
    check = today - timedelta(days=1)
    while check in log_days:
        streak += 1
        check -= timedelta(days=1)
    return streak


async def _call_gpt(user: User, today: date, ctx: dict) -> dict:
    """Build GPT prompt and return parsed suggestions dict."""
    name = user.first_name or "Chef"
    day_map = {
        "Monday": "Montag", "Tuesday": "Dienstag", "Wednesday": "Mittwoch",
        "Thursday": "Donnerstag", "Friday": "Freitag", "Saturday": "Samstag", "Sunday": "Sonntag",
    }
    day_name = day_map.get(today.strftime("%A"), today.strftime("%A"))

    lines = [f"Nutzer: {name} | Heute: {day_name}, {today.strftime('%d.%m.%Y')}\n"]

    if ctx["objectives"]:
        lines.append("AKTIVE ZIELE:")
        for o in ctx["objectives"][:5]:
            krs = [kr for kr in ctx["key_results"] if kr.objective_id == o.id]
            lines.append(f"  [{o.category}] {o.title}")
            for kr in krs[:3]:
                pct = 0
                if kr.target_value and kr.target_value > 0:
                    pct = min(100, int((kr.current_value / kr.target_value) * 100))
                lines.append(f"    KR: {kr.title} — {pct}%")

    if ctx["weekly_priorities"]:
        lines.append("\nDIESE WOCHE PRIORISIERTE DIMENSIONEN:")
        for wp in ctx["weekly_priorities"]:
            lines.append(f"  #{wp.priority_rank}: {wp.title}")

    mood_score = ctx["latest_mood"].data.get("score") if ctx["latest_mood"] else None
    if mood_score is not None:
        lines.append(f"\nLETZTE STIMMUNG: {mood_score}/10")

    lines.append(f"\nAKTIVITÄTS-STREAK: {ctx['streak']} Tage")
    lines.append(f"ROUTINE-STREAK: {ctx['routine_streak']} Tage")

    if ctx["last_reflection"]:
        r = ctx["last_reflection"]
        lines.append(f"\nLETZTE REFLECTION (KW{r.week_number}):")
        if r.biggest_win:
            lines.append(f"  Größter Win: {r.biggest_win}")
        if r.biggest_blocker:
            lines.append(f"  Größter Blocker: {r.biggest_blocker}")
        if r.week_score:
            lines.append(f"  Wochen-Score: {r.week_score}/10")

    # Log activity summary
    log_types: dict[str, int] = {}
    for log in ctx["recent_logs"]:
        log_types[log.log_type] = log_types.get(log.log_type, 0) + 1
    if log_types:
        summary = ", ".join(f"{v}× {k}" for k, v in log_types.items())
        lines.append(f"\nLOGS LETZTE 7 TAGE: {summary}")

    context_str = "\n".join(lines)

    system_prompt = (
        "Du bist ein persönlicher AI-COO. Analysiere die Daten und erstelle "
        "personalisierte Tagesempfehlungen auf Deutsch. Sei konkret, prägnant und motivierend."
    )

    user_prompt = f"""{context_str}

Erstelle heute personalisierte Empfehlungen als JSON mit exakt diesen Feldern:
{{
  "fokus_heute": [
    {{"task": "Aufgaben-Titel", "begruendung": "1-Satz Begründung warum heute"}},
    {{"task": "...", "begruendung": "..."}},
    {{"task": "...", "begruendung": "..."}}
  ],
  "tipp": "Ein konkreter, sofort umsetzbarer Produktivitäts-Tipp für heute",
  "streak_warnung": "Warnung falls ein aktiver Streak heute in Gefahr ist (oder null)",
  "dimension_check": "Hinweis falls eine diese Woche priorisierte Dimension vernachlässigt wird (oder null)"
}}

WICHTIG: Antworte NUR mit dem JSON-Objekt, kein weiterer Text."""

    try:
        response = await openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=600,
            temperature=0.7,
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content or "{}"
        data = json.loads(raw)
        return _validate_suggestions(data)
    except Exception:
        logger.exception("GPT-4o failed for daily suggestions, using fallback")
        return _fallback_suggestions(ctx)


def _validate_suggestions(data: dict) -> dict:
    """Ensure the returned dict has the expected shape."""
    fokus = data.get("fokus_heute", [])
    if not isinstance(fokus, list):
        fokus = []
    # Ensure 3 items, each with task + begruendung keys
    clean_fokus = []
    for item in fokus[:3]:
        if isinstance(item, dict):
            clean_fokus.append({
                "task": str(item.get("task", "")),
                "begruendung": str(item.get("begruendung", "")),
            })
    while len(clean_fokus) < 3:
        clean_fokus.append({"task": "—", "begruendung": ""})

    return {
        "fokus_heute": clean_fokus,
        "tipp": str(data.get("tipp", "")) if data.get("tipp") else "",
        "streak_warnung": str(data["streak_warnung"]) if data.get("streak_warnung") else None,
        "dimension_check": str(data["dimension_check"]) if data.get("dimension_check") else None,
    }


def _fallback_suggestions(ctx: dict) -> dict:
    fokus = []
    for o in ctx["objectives"][:3]:
        fokus.append({"task": o.title, "begruendung": "Aktives Ziel — bleib dran."})
    while len(fokus) < 3:
        fokus.append({"task": "—", "begruendung": ""})

    warnung = None
    if ctx["streak"] > 0:
        warnung = f"Du hast einen {ctx['streak']}-Tage-Streak! Vergiss dein Log heute nicht."

    return {
        "fokus_heute": fokus,
        "tipp": "Starte den Tag mit deiner wichtigsten Aufgabe, bevor du E-Mails checkst.",
        "streak_warnung": warnung,
        "dimension_check": None,
    }


async def get_or_generate_suggestions(
    session: AsyncSession, user: User, target_date: date
) -> dict | None:
    """Fetch existing suggestions for a date, or generate on-demand."""
    result = await session.execute(
        select(DailySuggestion).where(and_(
            DailySuggestion.user_id == user.id,
            DailySuggestion.date == target_date,
        ))
    )
    existing = result.scalar_one_or_none()
    if existing:
        return existing.suggestions

    # On-demand generation
    suggestion = await _generate_for_user(session, user, target_date)
    if suggestion:
        return suggestion.suggestions
    return None


# Alias for backward-compatible imports
send_daily_suggestions = generate_daily_suggestions
