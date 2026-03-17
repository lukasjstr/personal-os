"""Sprint 5: KR natural language update detector.

Detects progress updates in messages like:
  "5km gelaufen", "Sport heute erledigt", "3 Liter getrunken", "10 Liegestütze"
  → matches to user's active KeyResults → sends inline confirmation

Uses GPT-4o-mini for intent + value extraction, then fuzzy-matches to KRs.
"""
import json
import logging
import re
from typing import Optional

from openai import AsyncOpenAI
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup

from bot.config import settings
from bot.database.models import KeyResult, Objective, User
from bot.telegram.sender import send_message

logger = logging.getLogger(__name__)

_openai = AsyncOpenAI(api_key=settings.openai_api_key)

# In-memory state: pending KR confirmations per user
# user_id → {kr_id, new_value, old_value, action}
_pending_kr_updates: dict[int, dict] = {}


async def _load_active_krs(session: AsyncSession, user_id: int) -> list[KeyResult]:
    """Load all active KRs with their parent objectives."""
    res = await session.execute(
        select(KeyResult)
        .options(selectinload(KeyResult.objective))
        .where(and_(
            KeyResult.user_id == user_id,
            KeyResult.status == "active",
        ))
    )
    return res.scalars().all()


def _build_kr_summary(krs: list[KeyResult]) -> str:
    lines = []
    for kr in krs:
        obj_title = kr.objective.title if kr.objective else "?"
        unit = f" {kr.unit}" if kr.unit else ""
        target = f"/{kr.target_value}{unit}" if kr.target_value else ""
        lines.append(
            f"- KR #{kr.id}: '{kr.title}' (Ziel: {obj_title}) "
            f"[aktuell: {kr.current_value}{unit}{target}, typ: {kr.metric_type}]"
        )
    return "\n".join(lines) if lines else "Keine aktiven KRs."


async def detect_kr_update(
    text: str,
    user: User,
    session: AsyncSession,
) -> Optional[dict]:
    """Detect if text contains a KR progress update.

    Returns dict if match found:
      {kr_id, kr_title, objective_title, old_value, new_value, unit, action, confidence}
    Returns None if no KR update detected.
    """
    krs = await _load_active_krs(session, user.id)
    if not krs:
        return None

    kr_summary = _build_kr_summary(krs)

    system_prompt = """Du bist ein Fortschritts-Detektor für ein persönliches OKR-System.
Analysiere die Nachricht und prüfe ob sie einen Fortschritt für ein Key Result enthält.

Antworte NUR mit JSON:
{
  "is_kr_update": true/false,
  "kr_id": <int or null>,
  "extracted_value": <float or null>,
  "action": "add" | "set",
  "confidence": 0.0-1.0,
  "reason": "<kurze Erklärung>"
}

action="add" wenn der Wert addiert werden soll (z.B. "5km gelaufen" bei einem kumulativen KR)
action="set" wenn der Wert gesetzt werden soll (z.B. "Gewicht heute 82kg")
Nur matchen wenn confidence >= 0.7. Sonst is_kr_update=false."""

    user_prompt = f"""Aktive Key Results des Nutzers:
{kr_summary}

Nutzernachricht: "{text}"

Enthält diese Nachricht einen messbaren Fortschritt für eines der KRs?"""

    try:
        response = await _openai.chat.completions.create(
            model="gpt-4o-mini",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=200,
            temperature=0.1,
        )
        data = json.loads(response.choices[0].message.content)
    except Exception:
        logger.exception("KR update detection failed")
        return None

    if not data.get("is_kr_update") or data.get("confidence", 0) < 0.7:
        return None

    kr_id = data.get("kr_id")
    extracted_value = data.get("extracted_value")
    if not kr_id or extracted_value is None:
        return None

    # Find the KR
    matched_kr = next((kr for kr in krs if kr.id == kr_id), None)
    if not matched_kr:
        return None

    action = data.get("action", "add")
    old_value = matched_kr.current_value or 0.0
    new_value = old_value + extracted_value if action == "add" else float(extracted_value)

    # Cap at target if set
    if matched_kr.target_value and new_value > matched_kr.target_value:
        new_value = matched_kr.target_value

    return {
        "kr_id": matched_kr.id,
        "kr_title": matched_kr.title,
        "objective_title": matched_kr.objective.title if matched_kr.objective else None,
        "old_value": old_value,
        "new_value": new_value,
        "unit": matched_kr.unit or "",
        "action": action,
        "extracted_value": extracted_value,
        "target_value": matched_kr.target_value,
        "confidence": data.get("confidence", 0),
    }


async def send_kr_confirmation(bot: Bot, user: User, update_data: dict) -> None:
    """Send inline confirmation message for a detected KR update."""
    kr_id = update_data["kr_id"]
    kr_title = update_data["kr_title"]
    obj_title = update_data["objective_title"]
    old_val = update_data["old_value"]
    new_val = update_data["new_value"]
    unit = update_data["unit"]
    target = update_data["target_value"]

    # Store pending state
    _pending_kr_updates[user.id] = update_data

    # Progress bar
    progress_text = ""
    if target and target > 0:
        pct = min(100, int((new_val / target) * 100))
        filled = pct // 10
        bar = "█" * filled + "░" * (10 - filled)
        progress_text = f"\n[{bar}] {pct}%"

    lines = [
        f"📊 *KR-Update erkannt:*",
        f"*{kr_title}*",
    ]
    if obj_title:
        lines.append(f"📎 {obj_title}")

    action_emoji = "➕" if update_data["action"] == "add" else "🔄"
    lines.append(
        f"\n{action_emoji} {old_val}{unit} → *{new_val}{unit}*"
        + (f" / {target}{unit}" if target else "")
    )
    if progress_text:
        lines.append(progress_text)

    # Encode value as integer*100 to avoid float precision in callback_data
    new_val_encoded = int(round(new_val * 100))
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "✅ Bestätigen",
                callback_data=f"kr_confirm_{kr_id}_{new_val_encoded}",
            ),
            InlineKeyboardButton("❌ Abbrechen", callback_data="kr_cancel"),
        ]
    ])

    await bot.send_message(
        chat_id=user.telegram_id,
        text="\n".join(lines),
        parse_mode="Markdown",
        reply_markup=keyboard,
    )


async def handle_kr_confirm(
    bot: Bot,
    user: User,
    session: AsyncSession,
    kr_id: int,
    new_value_encoded: int,
) -> None:
    """Apply the confirmed KR update."""
    new_value = new_value_encoded / 100.0

    res = await session.execute(
        select(KeyResult).where(and_(KeyResult.id == kr_id, KeyResult.user_id == user.id))
    )
    kr = res.scalar_one_or_none()
    if not kr:
        await bot.send_message(chat_id=user.telegram_id, text="❌ KR nicht gefunden.")
        return

    old_value = kr.current_value or 0.0
    kr.current_value = new_value

    # Auto-complete if target reached
    if kr.target_value and new_value >= kr.target_value:
        kr.status = "completed"

    # Award XP
    user.xp = (user.xp or 0) + 5
    await session.commit()

    # Clear pending state
    _pending_kr_updates.pop(user.id, None)

    unit = kr.unit or ""
    target = kr.target_value
    completed_msg = " 🎉 *Ziel erreicht!*" if kr.status == "completed" else ""

    lines = [
        f"✅ *KR aktualisiert!*{completed_msg}",
        f"*{kr.title}*",
        f"{old_value}{unit} → *{new_value}{unit}*"
        + (f" / {target}{unit}" if target else ""),
        "+5 XP",
    ]
    await bot.send_message(
        chat_id=user.telegram_id,
        text="\n".join(lines),
        parse_mode="Markdown",
    )


async def handle_kr_cancel(bot: Bot, user: User) -> None:
    """Cancel a pending KR update."""
    _pending_kr_updates.pop(user.id, None)
    await bot.send_message(
        chat_id=user.telegram_id,
        text="❌ KR-Update abgebrochen.",
    )
