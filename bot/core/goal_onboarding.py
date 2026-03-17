"""Conversational Goal Onboarding — adaptive coaching dialog for new goals.

Flow:
1. User states a goal → start_onboarding() creates record, returns first question
2. Each answer → handle_onboarding_answer() stores answer, GPT decides next question or plan
3. Plan generated → presented with confirm/adjust/cancel buttons
4. On confirm → _execute_plan() creates everything via execute_accepted_proposal()
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Optional

from openai import AsyncOpenAI
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import settings
from bot.database.models import GoalOnboarding, Objective, OKRProposalDraft, User

logger = logging.getLogger(__name__)
_openai: AsyncOpenAI | None = None


def _get_openai() -> AsyncOpenAI:
    global _openai
    if _openai is None:
        _openai = AsyncOpenAI(api_key=settings.openai_api_key)
    return _openai


# ─── Public API ───────────────────────────────────────────────────────────────


async def get_active_onboarding(
    session: AsyncSession, user_id: int
) -> Optional[GoalOnboarding]:
    """Return the in-progress or plan_review onboarding, or None."""
    result = await session.execute(
        select(GoalOnboarding).where(
            and_(
                GoalOnboarding.user_id == user_id,
                GoalOnboarding.status.in_(["in_progress", "plan_review"]),
            )
        )
    )
    onboarding = result.scalar_one_or_none()
    # Auto-cancel stale sessions (>24h)
    if onboarding and onboarding.created_at:
        age = datetime.utcnow() - onboarding.created_at
        if age > timedelta(hours=24):
            onboarding.status = "cancelled"
            await session.flush()
            return None
    return onboarding


async def start_onboarding(
    session: AsyncSession, user_id: int, goal_text: str
) -> tuple[GoalOnboarding, str]:
    """Create a new GoalOnboarding and return (record, intro_message)."""
    # Cancel any existing in-progress onboarding
    existing = await get_active_onboarding(session, user_id)
    if existing:
        existing.status = "cancelled"
        await session.flush()

    first_question = await _generate_first_question(goal_text)

    onboarding = GoalOnboarding(
        user_id=user_id,
        status="in_progress",
        current_step=1,
        goal_input=goal_text,
        raw_answers={"q1_question": first_question},
    )
    session.add(onboarding)
    await session.flush()

    intro = (
        f"🎯 *Neues Ziel: {goal_text}*\n\n"
        "Lass mich dir ein paar Fragen stellen, damit ich den perfekten "
        "Plan für dich erstellen kann.\n\n"
        f"{first_question}"
    )
    return onboarding, intro


async def handle_onboarding_answer(
    session: AsyncSession,
    user: User,
    onboarding: GoalOnboarding,
    text: str,
) -> tuple[str, Optional[list[list[dict]]]]:
    """Process user's answer.

    Returns (reply_text, inline_keyboard_rows_or_none).
    Each keyboard row is a list of {"text": ..., "callback_data": ...} dicts.
    """
    if onboarding.status == "plan_review":
        return await _handle_plan_feedback(session, onboarding, text)
    return await _handle_question_answer(session, user, onboarding, text)


async def handle_onboarding_callback(
    session: AsyncSession,
    user: User,
    onboarding: GoalOnboarding,
    callback_data: str,
) -> str:
    """Handle inline button callbacks (confirm/adjust/cancel)."""
    if callback_data.startswith("goal_confirm_"):
        return await _execute_plan(session, user, onboarding)
    elif callback_data.startswith("goal_adjust_"):
        onboarding.status = "plan_review"
        await session.flush()
        return (
            "✏️ Was möchtest du am Plan ändern?\n\n"
            "Beschreib kurz, was angepasst werden soll "
            "(z.B. _mehr Routinen_, _anderer Zeitrahmen_, _weniger Tasks_)."
        )
    elif callback_data.startswith("goal_cancel_"):
        onboarding.status = "cancelled"
        await session.flush()
        return "❌ Ziel-Onboarding abgebrochen. Du kannst jederzeit ein neues starten mit /goal."
    return ""


async def cancel_onboarding(session: AsyncSession, user_id: int) -> bool:
    """Cancel any active onboarding. Returns True if one was cancelled."""
    active = await get_active_onboarding(session, user_id)
    if active:
        active.status = "cancelled"
        await session.flush()
        return True
    return False


# ─── Internal Q&A Logic ──────────────────────────────────────────────────────


async def _handle_question_answer(
    session: AsyncSession,
    user: User,
    onboarding: GoalOnboarding,
    text: str,
) -> tuple[str, Optional[list[list[dict]]]]:
    """Store answer, ask GPT for next question or generate plan."""
    step = onboarding.current_step
    raw = dict(onboarding.raw_answers or {})

    # Store answer
    question_text = raw.get(f"q{step}_question", "")
    raw[f"q{step}"] = {"question": question_text, "answer": text}
    onboarding.raw_answers = raw
    onboarding.current_step = step + 1
    await session.flush()

    # Ask GPT: next question or plan?
    decision = await _decide_next_step(onboarding)

    if decision["action"] == "ask":
        next_step = onboarding.current_step
        raw_updated = dict(onboarding.raw_answers or {})
        raw_updated[f"q{next_step}_question"] = decision["question"]
        onboarding.raw_answers = raw_updated
        await session.flush()
        return decision["question"], None

    if decision["action"] == "generate_plan":
        return await _generate_and_present_plan(session, user, onboarding)

    return "Etwas ist schiefgelaufen. Bitte versuche es erneut mit /goal.", None


# ─── GPT Decision Engine ─────────────────────────────────────────────────────


async def _generate_first_question(goal_text: str) -> str:
    """Generate the first coaching question based on the goal statement."""
    prompt = f"""Der Nutzer hat folgendes Ziel genannt: "{goal_text}"

Du bist ein empathischer Coach. Stelle EINE präzise, offene Frage auf Deutsch,
die dem Nutzer hilft, sein Ziel zu konkretisieren.

Fokus: Was genau will der Nutzer erreichen? Wie sieht Erfolg aus?

Antworte NUR mit der Frage (kein JSON, kein Markdown-Header).
Beginne die Frage mit einem passenden Emoji.
Halte sie unter 3 Sätzen."""

    try:
        client = _get_openai()
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200,
            temperature=0.6,
        )
        return (response.choices[0].message.content or "").strip()
    except Exception:
        logger.exception("Failed to generate first onboarding question")
        return "🎯 Was genau möchtest du erreichen? Beschreib dein Ziel so konkret wie möglich."


_FALLBACK_QUESTIONS = [
    "🎯 Was bedeutet Erfolg für dich konkret? Woran merkst du, dass du es geschafft hast?",
    "📅 Bis wann möchtest du das erreichen?",
    "💪 Welche Gewohnheiten oder täglichen Routinen brauchst du dafür?",
]


async def _decide_next_step(onboarding: GoalOnboarding) -> dict:
    """GPT decides: ask another question or generate plan."""
    raw = onboarding.raw_answers or {}
    step = onboarding.current_step  # Already incremented
    questions_asked = step - 1

    # Force plan after 7 questions
    if questions_asked >= 7:
        return {"action": "generate_plan"}

    # Build conversation history
    qa_lines = []
    for i in range(1, step):
        q_data = raw.get(f"q{i}", {})
        if isinstance(q_data, dict):
            qa_lines.append(f"Frage {i}: {q_data.get('question', '?')}")
            qa_lines.append(f"Antwort {i}: {q_data.get('answer', '?')}")

    prompt = f"""GOAL ONBOARDING — ENTSCHEIDUNG

Ursprüngliches Ziel: "{onboarding.goal_input}"

Bisheriges Gespräch:
{chr(10).join(qa_lines)}

Bisher gestellte Fragen: {questions_asked}

REGELN:
- Mindestens 3 Fragen (Klarheit, Messbarkeit, Zeitrahmen)
- Maximum 7 Fragen
- Einfache Ziele (Sport, Buch lesen, Wasser trinken): 3 Fragen reichen
- Komplexe Ziele (Karrierewechsel, Business, Studium): 5-7 Fragen
- KEINE Frage stellen die bereits beantwortet wurde
- Wenn genug Info für: Objective, 3+ KRs, 5+ Tasks, Routinen → generate_plan

Antworte NUR als JSON:
{{"action": "ask", "question": "Nächste Frage auf Deutsch mit Emoji"}}
ODER
{{"action": "generate_plan"}}"""

    try:
        client = _get_openai()
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
            temperature=0.4,
            response_format={"type": "json_object"},
        )
        decision = json.loads(response.choices[0].message.content or "{}")
    except Exception:
        logger.exception("Failed to decide next onboarding step")
        if questions_asked >= 3:
            return {"action": "generate_plan"}
        return {"action": "ask", "question": _FALLBACK_QUESTIONS[min(questions_asked, 2)]}

    # Force at least 3 questions
    if questions_asked < 3 and decision.get("action") == "generate_plan":
        return {"action": "ask", "question": _FALLBACK_QUESTIONS[min(questions_asked, 2)]}

    return decision


# ─── Plan Generation ─────────────────────────────────────────────────────────


async def _generate_and_present_plan(
    session: AsyncSession,
    user: User,
    onboarding: GoalOnboarding,
) -> tuple[str, Optional[list[list[dict]]]]:
    """Generate complete plan via GPT and present for confirmation."""
    raw = onboarding.raw_answers or {}
    qa_lines = []
    for i in range(1, onboarding.current_step):
        q_data = raw.get(f"q{i}", {})
        if isinstance(q_data, dict):
            qa_lines.append(f"Frage: {q_data.get('question', '?')}")
            qa_lines.append(f"Antwort: {q_data.get('answer', '?')}")

    # Load existing objectives for synergy
    obj_result = await session.execute(
        select(Objective).where(
            and_(Objective.user_id == user.id, Objective.status == "active")
        )
    )
    existing_titles = [o.title for o in obj_result.scalars().all()]

    plan = await _generate_full_plan(
        onboarding.goal_input, "\n".join(qa_lines), existing_titles
    )

    onboarding.draft_payload = plan
    onboarding.status = "plan_review"
    await session.flush()

    summary = _format_plan_summary(plan)
    keyboard = [[
        {"text": "✅ Erstellen", "callback_data": f"goal_confirm_{onboarding.id}"},
        {"text": "✏️ Anpassen", "callback_data": f"goal_adjust_{onboarding.id}"},
        {"text": "❌ Verwerfen", "callback_data": f"goal_cancel_{onboarding.id}"},
    ]]
    return summary, keyboard


async def _generate_full_plan(
    goal_text: str,
    conversation_context: str,
    existing_objectives: list[str],
) -> dict:
    """Call GPT-4o to generate the complete draft_payload."""
    from datetime import date

    today = date.today().isoformat()
    existing_str = ", ".join(existing_objectives) if existing_objectives else "Keine"

    system = (
        "Du bist ein strategischer Life-Coach und OKR-Experte. "
        "Generiere einen vollständigen, konkreten Aktionsplan. "
        "Antworte auf Deutsch. Sei präzise und actionable."
    )

    prompt = f"""Heute: {today}
Bestehende Ziele des Nutzers: {existing_str}

URSPRÜNGLICHES ZIEL: "{goal_text}"

COACHING-GESPRÄCH:
{conversation_context}

Generiere einen vollständigen Plan als JSON:
{{
  "objective": {{
    "title": "Inspirierender Titel max 80 Zeichen",
    "description": "2-3 Sätze basierend auf den Antworten",
    "category": "health|fitness|business|personal|finance|learning|relationships",
    "target_date": "YYYY-MM-DD",
    "emoji": "passendes Emoji",
    "priority_weight": 5
  }},
  "key_results": [
    {{
      "title": "Messbarer KR-Titel",
      "metric_type": "number|percentage|boolean|streak|checklist",
      "target_value": 10,
      "current_value": 0,
      "unit": "Einheit",
      "frequency": "daily|weekly|monthly|once"
    }}
  ],
  "tasks": [
    {{
      "title": "Konkreter erster Schritt",
      "priority": 1,
      "due_days": 1,
      "category": "general|shopping",
      "kr_title": "Titel des zugehörigen KR"
    }}
  ],
  "routines": [
    {{
      "title": "Wiederkehrende Gewohnheit",
      "frequency": "täglich|wöchentlich|3x pro Woche",
      "time_of_day": "morning|midday|evening|anytime",
      "kr_title": "Zugehöriger KR-Titel"
    }}
  ],
  "reminders": [
    {{
      "title": "Erinnerung",
      "message": "Push-Text max 80 Zeichen",
      "day_offset": 1,
      "time": "09:00"
    }}
  ],
  "shopping_items": ["Nur wenn wirklich nötig"],
  "motivation_message": "Persönliche Motivation",
  "first_step": "Erster konkreter Schritt HEUTE"
}}

REGELN:
- 3-5 Key Results, messbar und an Nutzer-Antworten orientiert
- 5-8 Tasks mit realistischen due_days
- 1-3 Routinen wenn Gewohnheitsänderung nötig
- 2-4 Erinnerungen für wichtige Meilensteine
- Shopping-Items nur wenn konkrete Anschaffungen nötig
- Alles auf Deutsch
- NUR valides JSON"""

    try:
        client = _get_openai()
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            max_tokens=1500,
            temperature=0.4,
            response_format={"type": "json_object"},
        )
        return json.loads(response.choices[0].message.content or "{}")
    except Exception:
        logger.exception("Failed to generate onboarding plan")
        return {
            "objective": {
                "title": goal_text[:80],
                "category": "personal",
                "description": goal_text,
            },
            "key_results": [],
            "tasks": [],
            "routines": [],
            "reminders": [],
            "shopping_items": [],
            "motivation_message": "",
            "first_step": "",
        }


def _format_plan_summary(plan: dict) -> str:
    """Format the plan as a readable Telegram message."""
    lines = ["🎯 *Dein Plan steht!*\n"]

    obj = plan.get("objective", {})
    emoji = obj.get("emoji", "🎯")
    lines.append(f"{emoji} *{obj.get('title', 'Neues Ziel')}*")
    if obj.get("description"):
        lines.append(f"_{obj['description']}_")
    if obj.get("target_date"):
        lines.append(f"📅 Zieldatum: {obj['target_date']}")
    lines.append("")

    krs = plan.get("key_results", [])
    if krs:
        lines.append("📊 *Key Results:*")
        for kr in krs:
            target = kr.get("target_value", "")
            unit = kr.get("unit", "")
            freq = kr.get("frequency", "")
            lines.append(f"  • {kr.get('title', '?')} ({target} {unit}, {freq})")
        lines.append("")

    tasks = plan.get("tasks", [])
    if tasks:
        lines.append(f"☐ *Tasks ({len(tasks)}):*")
        for t in tasks[:5]:
            lines.append(f"  • {t.get('title', '?')}")
        if len(tasks) > 5:
            lines.append(f"  _...und {len(tasks) - 5} weitere_")
        lines.append("")

    routines = plan.get("routines", [])
    if routines:
        lines.append("🔁 *Routinen:*")
        for r in routines:
            lines.append(f"  • {r.get('title', '?')} ({r.get('frequency', '?')})")
        lines.append("")

    shopping = plan.get("shopping_items", [])
    if shopping:
        lines.append("🛒 *Einkaufsliste:*")
        for item in shopping:
            lines.append(f"  • {item}")
        lines.append("")

    motivation = plan.get("motivation_message", "")
    if motivation:
        lines.append(f"💪 _{motivation}_")
        lines.append("")

    first_step = plan.get("first_step", "")
    if first_step:
        lines.append(f"➡️ *Erster Schritt heute:* {first_step}")

    return "\n".join(lines)


# ─── Plan Execution ──────────────────────────────────────────────────────────


async def _execute_plan(
    session: AsyncSession,
    user: User,
    onboarding: GoalOnboarding,
) -> str:
    """Execute the confirmed plan via the existing proposal pipeline."""
    from bot.core.proposal_execute import execute_accepted_proposal

    plan = onboarding.draft_payload
    if not plan:
        return "Fehler: Kein Plan vorhanden."

    # Create OKRProposalDraft row (the execution pipeline expects it)
    draft = OKRProposalDraft(
        user_id=user.id,
        source_text=onboarding.goal_input,
        draft_payload=plan,
        status="accepted",
    )
    session.add(draft)
    await session.flush()

    onboarding.proposal_draft_id = draft.id
    onboarding.status = "completed"
    onboarding.completed_at = datetime.utcnow()
    await session.flush()

    result = await execute_accepted_proposal(session, draft)

    # Build confirmation message
    obj_title = plan.get("objective", {}).get("title", "Neues Ziel")
    emoji = plan.get("objective", {}).get("emoji", "✅")
    lines = [f"{emoji} *{obj_title}* wurde erstellt!\n"]

    if result.key_result_ids:
        lines.append(f"📊 {len(result.key_result_ids)} Key Results")
    if result.task_ids:
        lines.append(f"☐ {len(result.task_ids)} Tasks")
    if result.calendar_event_ids:
        lines.append(f"📅 {len(result.calendar_event_ids)} Kalender-Events")
    if result.scheduled_reminder_ids:
        lines.append(f"⏰ {len(result.scheduled_reminder_ids)} Erinnerungen")

    first_step = plan.get("first_step", "")
    if first_step:
        lines.append(f"\n➡️ *Los geht's:* {first_step}")

    # Award XP
    try:
        from bot.core.gamification import add_xp
        await add_xp(user.id, 25, "goal_onboarding_complete", session)
        lines.append("\n🌟 +25 XP für dein neues Ziel!")
    except Exception:
        logger.debug("XP award failed (non-fatal)")

    return "\n".join(lines)


# ─── Plan Feedback / Adjustment ──────────────────────────────────────────────


async def _handle_plan_feedback(
    session: AsyncSession,
    onboarding: GoalOnboarding,
    feedback_text: str,
) -> tuple[str, Optional[list[list[dict]]]]:
    """Regenerate the plan based on user feedback (max 3 rounds)."""
    raw = dict(onboarding.raw_answers or {})
    feedback_count = raw.get("feedback_count", 0) + 1
    raw["feedback_count"] = feedback_count
    raw[f"feedback_{feedback_count}"] = feedback_text

    if feedback_count > 3:
        onboarding.raw_answers = raw
        onboarding.status = "cancelled"
        await session.flush()
        return (
            "Ich konnte den Plan nach 3 Anpassungen nicht perfekt machen. "
            "Starte gerne ein neues Onboarding mit /goal.",
            None,
        )

    old_plan = onboarding.draft_payload or {}
    qa_lines = []
    for i in range(1, onboarding.current_step):
        q_data = raw.get(f"q{i}", {})
        if isinstance(q_data, dict):
            qa_lines.append(f"Frage: {q_data.get('question', '')}")
            qa_lines.append(f"Antwort: {q_data.get('answer', '')}")

    adjusted_plan = await _regenerate_with_feedback(
        onboarding.goal_input, "\n".join(qa_lines), old_plan, feedback_text
    )

    onboarding.draft_payload = adjusted_plan
    onboarding.raw_answers = raw
    await session.flush()

    summary = "✏️ *Plan angepasst:*\n\n" + _format_plan_summary(adjusted_plan)
    keyboard = [[
        {"text": "✅ Erstellen", "callback_data": f"goal_confirm_{onboarding.id}"},
        {"text": "✏️ Anpassen", "callback_data": f"goal_adjust_{onboarding.id}"},
        {"text": "❌ Verwerfen", "callback_data": f"goal_cancel_{onboarding.id}"},
    ]]
    return summary, keyboard


async def _regenerate_with_feedback(
    goal_text: str,
    conversation_context: str,
    previous_plan: dict,
    feedback: str,
) -> dict:
    """Regenerate the plan incorporating user feedback."""
    from datetime import date

    prompt = f"""Heute: {date.today().isoformat()}

URSPRÜNGLICHES ZIEL: "{goal_text}"
COACHING-GESPRÄCH: {conversation_context}

VORHERIGER PLAN:
{json.dumps(previous_plan, ensure_ascii=False, indent=2)}

NUTZER-FEEDBACK:
"{feedback}"

Passe den Plan basierend auf dem Feedback an. Behalte alles was nicht kritisiert wurde.
Antworte NUR mit dem vollständigen angepassten JSON-Plan (gleiche Struktur wie vorher)."""

    try:
        client = _get_openai()
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1500,
            temperature=0.4,
            response_format={"type": "json_object"},
        )
        return json.loads(response.choices[0].message.content or "{}")
    except Exception:
        logger.exception("Failed to regenerate plan with feedback")
        return previous_plan
