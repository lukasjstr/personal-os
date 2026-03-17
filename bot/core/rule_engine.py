"""Feature 5: Automation Rule Engine — evaluate and execute user-defined Wenn-Dann rules."""
import logging
from datetime import datetime, timedelta, date
from typing import Optional

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import AutomationRule, Task, User

logger = logging.getLogger(__name__)


async def evaluate_rules(
    session: AsyncSession,
    user: User,
    trigger_type: str,
    event_data: dict,
) -> list[str]:
    """Find matching active rules, check cooldown, execute actions.

    Returns list of action result messages.
    """
    now = datetime.utcnow()

    result = await session.execute(
        select(AutomationRule).where(
            and_(
                AutomationRule.user_id == user.id,
                AutomationRule.trigger_type == trigger_type,
                AutomationRule.is_active == True,  # noqa: E712
            )
        )
    )
    rules = result.scalars().all()

    messages: list[str] = []
    for rule in rules:
        # Check cooldown
        if rule.last_triggered_at:
            elapsed_hours = (now - rule.last_triggered_at).total_seconds() / 3600
            if elapsed_hours < rule.cooldown_hours:
                logger.debug(
                    "Rule %s skipped (cooldown: %.1fh remaining)",
                    rule.id,
                    rule.cooldown_hours - elapsed_hours,
                )
                continue

        # Check trigger conditions if any
        if not _check_conditions(rule.trigger_conditions or {}, event_data):
            continue

        try:
            msg = await execute_rule(session, user, rule, event_data)
            if msg:
                messages.append(msg)

            # Update rule stats
            rule.last_triggered_at = now
            rule.trigger_count = (rule.trigger_count or 0) + 1
            await session.flush()
        except Exception:
            logger.exception("Error executing rule %s for user %s", rule.id, user.id)

    return messages


def _check_conditions(conditions: dict, event_data: dict) -> bool:
    """Check if event_data satisfies rule trigger conditions."""
    if not conditions:
        return True

    # Numeric threshold checks
    threshold = conditions.get("threshold")
    if threshold is not None:
        value_key = conditions.get("value_key", "value")
        event_value = event_data.get(value_key)
        if event_value is None:
            return False
        operator = conditions.get("operator", "lte")
        if operator == "lte" and event_value > threshold:
            return False
        if operator == "gte" and event_value < threshold:
            return False
        if operator == "eq" and event_value != threshold:
            return False

    # Keyword match for routine_skipped
    routine_keyword = conditions.get("routine_keyword")
    if routine_keyword:
        routine_title = event_data.get("routine_title", "").lower()
        if routine_keyword.lower() not in routine_title:
            return False

    # Days skipped threshold
    days = conditions.get("days")
    if days is not None:
        event_days = event_data.get("days_skipped", 0)
        if event_days < days:
            return False

    return True


async def execute_rule(
    session: AsyncSession,
    user: User,
    rule: AutomationRule,
    event_data: dict,
    bot=None,
) -> str:
    """Execute the action defined in a rule. Returns result message."""
    action_type = rule.action_type
    params = rule.action_params or {}

    if action_type == "send_message":
        message = params.get("message", rule.title)
        # Send via Telegram if bot available
        if bot:
            try:
                await bot.send_message(chat_id=user.telegram_id, text=message)
            except Exception:
                logger.exception("Failed to send Telegram message for rule %s", rule.id)
        else:
            # Try to get bot from sender
            try:
                from bot.telegram.sender import send_message as _send
                await _send(user.telegram_id, message)
            except Exception:
                logger.exception("Failed to send message for rule %s", rule.id)
        return f"Nachricht gesendet: {message[:80]}"

    elif action_type == "create_task":
        title = params.get("title", "Automatisch erstellter Task")
        priority = params.get("priority", 3)
        due_offset_days = params.get("due_offset_days", 1)
        due = date.today() + timedelta(days=due_offset_days)

        task = Task(
            user_id=user.id,
            title=title,
            priority=priority,
            due_date=due,
            status="todo",
            category=params.get("category", "general"),
        )
        session.add(task)
        await session.flush()
        return f"Task erstellt: {title} (fällig {due})"

    elif action_type == "reschedule_workout":
        # Create a follow-up workout task for tomorrow
        title = params.get("title", "Nachholtraining")
        due = date.today() + timedelta(days=1)
        task = Task(
            user_id=user.id,
            title=title,
            priority=1,
            due_date=due,
            status="todo",
            category="general",
        )
        session.add(task)
        await session.flush()
        return f"Workout umgeplant auf morgen: {title}"

    elif action_type == "suggest_routine":
        routine_name = params.get("routine_name", "Routine")
        msg = f"💡 Erinnerung: Hast du heute deine {routine_name} gemacht?"
        try:
            from bot.telegram.sender import send_message as _send
            await _send(user.telegram_id, msg)
        except Exception:
            pass
        return f"Routine-Erinnerung gesendet: {routine_name}"

    elif action_type == "update_setting":
        setting_key = params.get("key")
        setting_value = params.get("value")
        if setting_key:
            settings_dict = dict(user.settings or {})
            settings_dict[setting_key] = setting_value
            user.settings = settings_dict
            await session.flush()
            return f"Einstellung aktualisiert: {setting_key} = {setting_value}"

    return f"Aktion ausgeführt: {action_type}"


async def get_rule_templates() -> list[dict]:
    """Return pre-built automation rule templates."""
    return [
        {
            "id": "workout_skipped_reschedule",
            "title": "Workout verpasst → morgen neu einplanen",
            "description": "Wenn ein Workout übersprungen wird, wird automatisch ein Nachholtraining für morgen erstellt.",
            "trigger_type": "workout_skipped",
            "trigger_conditions": None,
            "action_type": "create_task",
            "action_params": {
                "title": "Nachholtraining",
                "priority": 1,
                "due_offset_days": 1,
            },
            "cooldown_hours": 24,
        },
        {
            "id": "energy_low_no_deepwork",
            "title": "Energie niedrig → Deep Work entfernen",
            "description": "Wenn die Energie unter 4 fällt, wird eine Nachricht gesendet, Deep-Work-Tasks zu vermeiden.",
            "trigger_type": "energy_low",
            "trigger_conditions": {"threshold": 4, "value_key": "energy", "operator": "lte"},
            "action_type": "send_message",
            "action_params": {
                "message": "⚡ Deine Energie ist niedrig — heute keine Deep-Work-Tasks. Fokussiere auf leichte, administrative Aufgaben.",
            },
            "cooldown_hours": 12,
        },
        {
            "id": "kr_completed_congrats",
            "title": "KR 100% erreicht → Gratulation + nächste KR vorschlagen",
            "description": "Wenn ein Key Result abgeschlossen wird, wird eine Glückwunschnachricht gesendet.",
            "trigger_type": "kr_completed",
            "trigger_conditions": None,
            "action_type": "send_message",
            "action_params": {
                "message": "🎉 Glückwunsch! Du hast ein Key Result zu 100% abgeschlossen! Zeit, das nächste anzugehen.",
            },
            "cooldown_hours": 1,
        },
        {
            "id": "sleep_low_reduce_intensity",
            "title": "Schlechter Schlaf + Training heute → Intensität reduzieren",
            "description": "Wenn die Schlafqualität unter 6 Stunden liegt, wird empfohlen, das Training zu reduzieren.",
            "trigger_type": "sleep_low",
            "trigger_conditions": {"threshold": 6, "value_key": "sleep_hours", "operator": "lte"},
            "action_type": "send_message",
            "action_params": {
                "message": "😴 HRV/Schlaf niedrig — heute leichtes Training oder Ruhetag empfohlen. Höre auf deinen Körper.",
            },
            "cooldown_hours": 20,
        },
        {
            "id": "journal_reminder",
            "title": "3 Tage kein Journal → sanfte Erinnerung",
            "description": "Wenn das Journal 3 Tage nicht ausgefüllt wurde, wird eine Erinnerung gesendet.",
            "trigger_type": "routine_skipped",
            "trigger_conditions": {"routine_keyword": "journal", "days": 3},
            "action_type": "send_message",
            "action_params": {
                "message": "📓 Du hast seit 3 Tagen nicht journalisiert. Wie war deine Woche bisher? Nimm dir 5 Minuten für deine Gedanken.",
            },
            "cooldown_hours": 72,
        },
    ]
