"""Life Profile — persistent compressed life memory updated weekly."""
import logging
from datetime import datetime, timedelta

from openai import AsyncOpenAI
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import settings
from bot.database.models import (
    EveningCheckin, KeyResult, Log, Objective,
    Task, UserInsight, WeeklyReflection, LifeProfile,
)

logger = logging.getLogger(__name__)
_openai = AsyncOpenAI(api_key=settings.openai_api_key)


async def update_life_profile(session: AsyncSession, user_id: int) -> "LifeProfile":
    """Generate/update compressed life profile using GPT-4o.

    Pulls last 30 days of logs, completed tasks, KR progress, reflections, insights.
    Generates a 400-500 word profile + strengths list + patterns list + current_focus.
    """
    since = datetime.utcnow() - timedelta(days=30)

    # Load completed tasks
    tasks_res = await session.execute(
        select(Task).where(and_(
            Task.user_id == user_id,
            Task.status == "done",
            Task.completed_at >= since,
        )).order_by(Task.completed_at.desc()).limit(30)
    )
    completed_tasks = tasks_res.scalars().all()

    # Load active objectives with KRs
    objs_res = await session.execute(
        select(Objective).where(and_(
            Objective.user_id == user_id,
            Objective.status == "active",
        ))
    )
    objectives = objs_res.scalars().all()

    # Load recent reflections
    refl_res = await session.execute(
        select(WeeklyReflection).where(and_(
            WeeklyReflection.user_id == user_id,
            WeeklyReflection.created_at >= since,
        )).order_by(WeeklyReflection.created_at.desc()).limit(4)
    )
    reflections = refl_res.scalars().all()

    # Load recent insights
    insight_res = await session.execute(
        select(UserInsight).where(and_(
            UserInsight.user_id == user_id,
            UserInsight.is_active == True,  # noqa: E712
        )).limit(10)
    )
    insights = insight_res.scalars().all()

    # Load recent mood logs
    mood_res = await session.execute(
        select(Log).where(and_(
            Log.user_id == user_id,
            Log.log_type == "mood",
            Log.logged_at >= since,
        )).order_by(Log.logged_at.desc()).limit(20)
    )
    moods = mood_res.scalars().all()

    # Build context
    context_parts = []

    if objectives:
        context_parts.append("=== AKTIVE ZIELE ===")
        for obj in objectives:
            context_parts.append(f"- {obj.title} [{obj.category}] (Status: {obj.status})")

    if completed_tasks:
        context_parts.append(f"\n=== ERLEDIGTE TASKS (letzte 30 Tage, {len(completed_tasks)} Stück) ===")
        for t in completed_tasks[:15]:
            context_parts.append(f"- {t.title}")

    if reflections:
        context_parts.append("\n=== WÖCHENTLICHE REFLEXIONEN ===")
        for r in reflections:
            if r.ai_summary:
                context_parts.append(f"- KW {r.week_start}: {r.ai_summary[:200]}")

    if insights:
        context_parts.append("\n=== ERKANNTE MUSTER ===")
        for ins in insights:
            context_parts.append(f"- {ins.title}: {ins.description[:150]}")

    if moods:
        scores = [m.data.get("score", 0) for m in moods if isinstance(m.data, dict)]
        if scores:
            avg_mood = sum(scores) / len(scores)
            context_parts.append(f"\n=== STIMMUNG (Durchschnitt 30 Tage): {avg_mood:.1f}/10 ===")

    data_context = "\n".join(context_parts) if context_parts else "Keine ausreichenden Daten vorhanden."

    # Get existing profile for continuity
    existing_res = await session.execute(
        select(LifeProfile).where(LifeProfile.user_id == user_id)
    )
    existing = existing_res.scalar_one_or_none()
    prev_summary = existing.summary if existing and existing.summary else ""

    prompt = f"""Du bist ein persönlicher Life Coach. Erstelle ein komprimiertes Lebensprofil (400-500 Wörter) auf Basis der Daten des Nutzers.

VORHERIGES PROFIL (falls vorhanden, zur Kontinuität):
{prev_summary[:500] if prev_summary else "(Erstes Profil)"}

AKTUELLE DATEN (letzte 30 Tage):
{data_context}

Erstelle ein JSON-Objekt mit folgenden Feldern:
{{
  "summary": "400-500 Wörter Lebensprofil — wer ist dieser Mensch, was treibt ihn an, wo steht er gerade",
  "strengths": ["Stärke 1", "Stärke 2", "Stärke 3", "Stärke 4", "Stärke 5"],
  "patterns": ["Verhaltensmuster 1", "Verhaltensmuster 2", "Verhaltensmuster 3"],
  "current_focus": "Was ist aktuell der wichtigste Fokus/Priorität (1-2 Sätze)"
}}

Antworte NUR mit dem JSON-Objekt. Sei konkret, direkt und datenbasiert."""

    try:
        response = await _openai.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1200,
            temperature=0.7,
            response_format={"type": "json_object"},
        )
        import json
        data = json.loads(response.choices[0].message.content)
        summary = data.get("summary", "")
        strengths = data.get("strengths", [])
        patterns = data.get("patterns", [])
        current_focus = data.get("current_focus", "")
    except Exception:
        logger.exception("GPT-4o failed for life profile generation")
        summary = f"Profil-Update fehlgeschlagen. {len(completed_tasks)} Tasks abgeschlossen, {len(objectives)} aktive Ziele."
        strengths = []
        patterns = []
        current_focus = ""

    if existing:
        existing.summary = summary
        existing.strengths = strengths
        existing.patterns = patterns
        existing.current_focus = current_focus
        existing.last_updated = datetime.utcnow()
        existing.update_count = (existing.update_count or 0) + 1
        await session.flush()
        return existing
    else:
        profile = LifeProfile(
            user_id=user_id,
            summary=summary,
            strengths=strengths,
            patterns=patterns,
            current_focus=current_focus,
            last_updated=datetime.utcnow(),
            update_count=1,
        )
        session.add(profile)
        await session.flush()
        return profile


async def get_life_profile_context(session: AsyncSession, user_id: int) -> str:
    """Return profile as context block for AI. Returns '' if no profile yet."""
    res = await session.execute(
        select(LifeProfile).where(LifeProfile.user_id == user_id)
    )
    profile = res.scalar_one_or_none()
    if not profile or not profile.summary:
        return ""

    date_str = profile.last_updated.strftime("%d.%m.%Y") if profile.last_updated else "unbekannt"
    lines = [f"=== LEBENS-PROFIL (Stand: {date_str}) ==="]
    lines.append(profile.summary)

    if profile.strengths:
        lines.append(f"Stärken: {', '.join(profile.strengths)}")

    if profile.patterns:
        for p in profile.patterns:
            lines.append(f"• {p}")

    if profile.current_focus:
        lines.append(f"Fokus: {profile.current_focus}")

    return "\n".join(lines)


# ─── V3 P02 — Bedrock layer ──────────────────────────────────────────────────


def format_bedrock(bedrock: dict) -> str:
    """Render the bedrock dict as the hard-coded WER-DU-FÜHRST block."""
    if not bedrock:
        return ""
    identity = bedrock.get("identity") or {}
    name = identity.get("name", "der Nutzer")
    location = identity.get("current_location", "unbekannt")
    company = identity.get("company")
    co_founders = identity.get("co_founders") or []
    launch = identity.get("launch_target")

    lines: list[str] = ["━━━ WER DU FÜHRST ━━━"]

    intro_parts = [f"{name}, basiert in {location}"]
    if company:
        co = f" mit {', '.join(co_founders)}" if co_founders else ""
        intro_parts.append(f"Co-Founder von {company}{co}")
    lines.append(", ".join(intro_parts) + ".")
    if launch:
        lines.append(f"Launch-Ziel: {launch}.")

    leitspruch = bedrock.get("leitspruch")
    if leitspruch:
        lines.append("")
        lines.append("LEITSPRUCH (zitiere bei Bedarf):")
        lines.append(f'"{leitspruch}"')

    bottleneck = bedrock.get("bottleneck")
    weaknesses = bedrock.get("weaknesses") or []
    if bottleneck or weaknesses:
        lines.append("")
        lines.append("BOTTLENECK (immer im Hinterkopf):")
        bn_parts = []
        if bottleneck:
            bn_parts.append(bottleneck)
        if weaknesses:
            bn_parts.append(f"Schwächen: {', '.join(weaknesses)}")
        lines.append(" — ".join(bn_parts))

    life_areas = bedrock.get("life_areas") or []
    if life_areas:
        lines.append("")
        lines.append("9 LEBENSBEREICHE (jeder Vorschlag muss darauf einzahlen oder eine Lücke aufzeigen):")
        for i, area in enumerate(life_areas, start=1):
            n = area.get("name", "?")
            v = area.get("vision", "")
            lines.append(f"{i}. {n}: {v}")

    levers = bedrock.get("skill_levers") or []
    if levers:
        lines.append("")
        lines.append("4 SKILL-HEBEL (Priority 1 = kritisch):")
        for lever in sorted(levers, key=lambda x: x.get("priority", 99)):
            n = lever.get("name", "?")
            d = lever.get("description", "")
            p = lever.get("priority", "?")
            lines.append(f"P{p} {n}: {d}")

    comp = bedrock.get("self_leadership_competencies") or []
    if comp:
        lines.append("")
        lines.append("10 SELBSTFÜHRUNGS-KOMPETENZEN:")
        for i, c in enumerate(comp, start=1):
            lines.append(f"  {i}. {c}")

    style = bedrock.get("communication_style")
    if style:
        lines.append("")
        lines.append(f"KOMMUNIKATIONS-STIL: {style}")

    lines.append("━━━━━━━━━━━━━━━━━━━━")
    return "\n".join(lines)


async def get_bedrock_context(session: AsyncSession, user_id: int) -> str:
    """Return the bedrock block for AI context, or '' if not seeded yet."""
    res = await session.execute(
        select(LifeProfile).where(LifeProfile.user_id == user_id)
    )
    profile = res.scalar_one_or_none()
    if not profile or not profile.bedrock:
        return ""
    return format_bedrock(profile.bedrock)


async def update_bedrock(session: AsyncSession, user_id: int, new_bedrock: dict, source: str = "api") -> "LifeProfile":
    """Update bedrock for a user, archiving the previous version to history.

    Creates a LifeProfile row if none exists.
    """
    res = await session.execute(
        select(LifeProfile).where(LifeProfile.user_id == user_id)
    )
    profile = res.scalar_one_or_none()
    now = datetime.utcnow()

    if profile is None:
        profile = LifeProfile(
            user_id=user_id,
            bedrock=new_bedrock,
            bedrock_updated_at=now,
            bedrock_history=[{"snapshot": new_bedrock, "ts": now.isoformat(), "source": source}],
        )
        session.add(profile)
        await session.flush()
        return profile

    history = list(profile.bedrock_history or [])
    if profile.bedrock:
        history.append({
            "snapshot": profile.bedrock,
            "ts": (profile.bedrock_updated_at or now).isoformat(),
            "source": "pre-update-archive",
        })
    history.append({"snapshot": new_bedrock, "ts": now.isoformat(), "source": source})
    profile.bedrock = new_bedrock
    profile.bedrock_updated_at = now
    profile.bedrock_history = history
    await session.flush()
    return profile
