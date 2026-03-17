"""Smart Detector — auto-detects journal entries, gratitude, and free evening reports.

When a user sends a relevant message, we:
1. Store it in UserDocument (append to today's date)
2. Update the matching KeyResult streak
3. Return a confirmation message

This closes the loops:
- Journal: user types entry → stored → KR streak +1
- Gratitude: user types 3 things → stored → KR streak +1
"""
import json
import logging
from datetime import date, datetime
from typing import Optional

from openai import AsyncOpenAI
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import settings
from bot.database.models import KeyResult, User, UserDocument

logger = logging.getLogger(__name__)
_openai = AsyncOpenAI(api_key=settings.openai_api_key)

# In-memory state: pending prompts per user
# user_id → {"type": "journal"|"gratitude", "prompted_at": datetime}
_pending_prompts: dict[int, dict] = {}


def set_pending_prompt(user_id: int, prompt_type: str) -> None:
    """Mark that this user was just prompted for journal/gratitude (for 30min window)."""
    _pending_prompts[user_id] = {"type": prompt_type, "prompted_at": datetime.utcnow()}


def get_pending_prompt(user_id: int) -> Optional[str]:
    """Return active prompt type if within 60-minute window, else None."""
    state = _pending_prompts.get(user_id)
    if not state:
        return None
    elapsed = (datetime.utcnow() - state["prompted_at"]).total_seconds()
    if elapsed > 3600:
        _pending_prompts.pop(user_id, None)
        return None
    return state["type"]


def clear_pending_prompt(user_id: int) -> None:
    _pending_prompts.pop(user_id, None)


# ── Keyword shortcuts (no GPT needed for these) ────────────────────────────
_JOURNAL_KEYWORDS = [
    "journal:", "tagebuch:", "heute war", "heute habe ich", "ich habe heute",
    "mein tag", "tag heute", "reflexion:", "reflection:", "heute gelernt",
]
_GRATITUDE_KEYWORDS = [
    "dankbar:", "dankbarkeit:", "ich bin dankbar", "3 dinge:", "drei dinge:",
    "grateful:", "dankbar für", "heute dankbar", "dankbarkeit heute",
]


def _quick_detect(text: str) -> Optional[str]:
    """Fast keyword-based detection. Returns 'journal', 'gratitude', or None."""
    lower = text.lower().strip()
    for kw in _GRATITUDE_KEYWORDS:
        if lower.startswith(kw) or kw in lower[:80]:
            return "gratitude"
    for kw in _JOURNAL_KEYWORDS:
        if lower.startswith(kw) or kw in lower[:80]:
            return "journal"
    return None


async def _gpt_classify(text: str, pending_type: Optional[str]) -> Optional[str]:
    """Use GPT-4o-mini to classify ambiguous text. Only called for longer texts."""
    if len(text) < 30:
        return None

    context = f"Der Nutzer wurde gerade nach seinem {pending_type} gefragt." if pending_type else ""

    prompt = f"""{context}
Klassifiziere diese Nutzernachricht:

"{text[:400]}"

Antworte NUR mit JSON:
{{"type": "journal"|"gratitude"|"none", "confidence": 0.0-1.0}}

journal = persönliche Reflexion, Tagebucheintrag, Tagesrückblick
gratitude = Dankbarkeit, 3 Dinge, wofür bin ich dankbar
none = etwas anderes (Aufgaben, Einkauf, Fragen, Befehle)
Nur matchen wenn confidence >= 0.75"""

    try:
        resp = await _openai.chat.completions.create(
            model="gpt-4o-mini",
            response_format={"type": "json_object"},
            messages=[{"role": "user", "content": prompt}],
            max_tokens=60,
            temperature=0.1,
        )
        data = json.loads(resp.choices[0].message.content)
        if data.get("confidence", 0) >= 0.75 and data.get("type") != "none":
            return data["type"]
    except Exception:
        logger.debug("GPT classify failed, skipping")
    return None


async def _get_or_create_document(
    session: AsyncSession, user_id: int, title: str, emoji: str
) -> UserDocument:
    """Get or create a UserDocument by title."""
    res = await session.execute(
        select(UserDocument).where(
            and_(UserDocument.user_id == user_id, UserDocument.title == title)
        )
    )
    doc = res.scalar_one_or_none()
    if not doc:
        doc = UserDocument(
            user_id=user_id,
            title=title,
            emoji=emoji,
            content="",
            sort_order=0,
        )
        session.add(doc)
        await session.flush()
    return doc


async def _append_to_document(doc: UserDocument, text: str, entry_type: str) -> None:
    """Append an entry to a document with date header."""
    today = date.today()
    date_str = today.strftime("%d.%m.%Y")
    separator = "\n\n---\n\n"
    entry = f"**{date_str}**\n{text.strip()}"
    if doc.content:
        doc.content = doc.content + separator + entry
    else:
        doc.content = entry


async def _update_kr_streak(session: AsyncSession, user_id: int, kr_keywords: list[str]) -> Optional[KeyResult]:
    """Find and increment a KeyResult by keyword matching on title."""
    res = await session.execute(
        select(KeyResult).where(and_(
            KeyResult.user_id == user_id,
            KeyResult.status == "active",
        ))
    )
    krs = res.scalars().all()
    for kr in krs:
        title_lower = kr.title.lower()
        for kw in kr_keywords:
            if kw in title_lower:
                kr.current_value = (kr.current_value or 0) + 1
                # Auto-complete if target reached
                if kr.target_value and kr.current_value >= kr.target_value:
                    kr.status = "completed"
                return kr
    return None


async def handle_journal_entry(
    session: AsyncSession,
    user: User,
    text: str,
) -> str:
    """Store journal entry, update KR, return confirmation."""
    # Store in "Tagebuch" document
    doc = await _get_or_create_document(session, user.id, "Tagebuch", "📓")
    await _append_to_document(doc, text, "journal")

    # Update journaling KR
    kr = await _update_kr_streak(session, user.id, ["journal", "tagebuch"])
    kr_msg = ""
    if kr:
        pct = int((kr.current_value / kr.target_value * 100)) if kr.target_value else 0
        kr_msg = f"\n📈 {kr.title}: {int(kr.current_value)}/{int(kr.target_value or 0)} Tage"
        if kr.status == "completed":
            kr_msg += " 🎉"

    # Award XP
    user.xp = (user.xp or 0) + 5

    clear_pending_prompt(user.id)

    return (
        f"📓 *Journal gespeichert!* +5 XP{kr_msg}\n\n"
        f"_{text[:100]}{'...' if len(text) > 100 else ''}_\n\n"
        "Weiter so — Reflexion macht dich besser. 💪"
    )


async def handle_gratitude_entry(
    session: AsyncSession,
    user: User,
    text: str,
) -> str:
    """Store gratitude entry, update KR, return confirmation."""
    doc = await _get_or_create_document(session, user.id, "Dankbarkeit", "🙏")
    await _append_to_document(doc, text, "gratitude")

    kr = await _update_kr_streak(session, user.id, ["dankbar", "gratitude"])
    kr_msg = ""
    if kr:
        pct = int((kr.current_value / kr.target_value * 100)) if kr.target_value else 0
        kr_msg = f"\n📈 {kr.title}: {int(kr.current_value)}/{int(kr.target_value or 0)} Wochen"

    user.xp = (user.xp or 0) + 3

    clear_pending_prompt(user.id)

    return (
        f"🙏 *Dankbarkeit gespeichert!* +3 XP{kr_msg}\n\n"
        f"_{text[:120]}{'...' if len(text) > 120 else ''}_\n\n"
        "Dankbarkeit ist Stärke. 🌟"
    )


async def detect_and_handle(
    session: AsyncSession,
    user: User,
    text: str,
) -> Optional[str]:
    """Main entry point. Returns reply string if handled, None if not detected.

    Call this BEFORE sending to GPT.
    """
    # Check if user was recently prompted (higher confidence)
    pending = get_pending_prompt(user.id)

    # Fast keyword check
    detected = _quick_detect(text)

    # If not detected by keywords but user was prompted and text is substantial
    if not detected and pending and len(text) >= 20:
        detected = await _gpt_classify(text, pending)

    # If still not detected and text is long enough, try GPT
    if not detected and len(text) >= 60:
        detected = await _gpt_classify(text, None)

    if detected == "journal":
        return await handle_journal_entry(session, user, text)
    elif detected == "gratitude":
        return await handle_gratitude_entry(session, user, text)

    return None
