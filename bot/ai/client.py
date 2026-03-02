"""OpenAI client — GPT-4o with function calling and next-action principle."""
import json
import logging
from datetime import date, datetime
from typing import Any, Optional

from openai import AsyncOpenAI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.ai.context import build_context
from bot.ai.prompts import SYSTEM_PROMPT
from bot.ai.tools import TOOLS
from bot.config import settings
from bot.core.brain_dumps import create_brain_dump
from bot.core.calendar import create_calendar_event
from bot.core.logs import log_food, log_mood, log_progress, log_water, log_workout
from bot.core.objectives import (
    create_key_result,
    create_objective,
    get_active_objectives,
    get_progress_report,
    suggest_tasks_for_objective,
)
from bot.core.priorities import get_todays_priorities
from bot.core.routines import complete_routine, create_routine, get_active_routines, get_todays_completions
from bot.core.shopping import complete_shopping, get_shopping_summary
from bot.core.tasks import (
    complete_task,
    create_task,
    get_next_task_in_kr,
    get_open_tasks,
    search_logs,
    update_task_status,
)
from bot.core.fitness import create_fitness_split, get_fitness_plan as _get_fitness_plan
from bot.core.user_settings import update_setting
from bot.core.achievements import check_achievements, format_achievement_message
from bot.database.models import Conversation, ShoppingDefault, Task, User

logger = logging.getLogger(__name__)

openai_client = AsyncOpenAI(api_key=settings.openai_api_key)


async def _notify_achievements(session: AsyncSession, user: User) -> None:
    """Check achievements and send Telegram notifications for newly unlocked ones."""
    try:
        from bot.telegram.sender import send_message
        newly_unlocked = await check_achievements(user.id, session)
        for achievement in newly_unlocked:
            await send_message(user.telegram_id, format_achievement_message(achievement))
    except Exception as e:
        logger.warning("Achievement check failed: %s", e)


async def _execute_tool(
    name: str,
    args: dict[str, Any],
    session: AsyncSession,
    user: User,
) -> str:
    """Execute a tool call and return a string result."""
    try:
        # ─── OKR ──────────────────────────────────────────────────────────────
        if name == "create_objective":
            obj = await create_objective(session, user.id, **args)
            await _notify_achievements(session, user)
            return (
                f"✅ Objective #{obj.id} erstellt: *{obj.title}* [{obj.category}]\n"
                f"→ Jetzt suggest_tasks_for_objective aufrufen um konkrete Tasks zu erstellen."
            )

        elif name == "create_key_result":
            kr = await create_key_result(session, user.id, **args)
            return (
                f"✅ Key Result #{kr.id} erstellt: *{kr.title}*\n"
                f"   Metrik: {kr.metric_type}, Ziel: {kr.target_value} {kr.unit or ''}, Frequenz: {kr.frequency}"
            )

        # ─── Tasks ────────────────────────────────────────────────────────────
        elif name == "create_task":
            task = await create_task(session, user.id, **args)
            cat = f" [{task.category}]" if task.category != "general" else ""
            return f"✅ Task #{task.id} erstellt: *{task.title}*{cat} [P{task.priority}]"

        elif name == "complete_task":
            task = await complete_task(session, user.id, args["task_id"])
            if not task:
                return f"Task #{args['task_id']} nicht gefunden."
            result = f"✅ *{task.title}* erledigt!"
            # Next-action principle
            if task.key_result_id:
                next_task = await get_next_task_in_kr(session, task.key_result_id)
                if next_task:
                    result += f"\n\n➡️ *NÄCHSTE AKTION:* {next_task.title} (Task #{next_task.id})"
            await _notify_achievements(session, user)
            return result

        elif name == "update_task_status":
            task = await update_task_status(session, user.id, args["task_id"], args["status"])
            if not task:
                return f"Task #{args['task_id']} nicht gefunden."
            return f"Task #{task.id} Status → {args['status']}"

        # ─── Shopping ─────────────────────────────────────────────────────────
        elif name == "get_shopping_list":
            return await get_shopping_summary(session, user.id)

        elif name == "complete_shopping":
            item_ids = args.get("item_ids") or []
            count = await complete_shopping(session, user.id, item_ids if item_ids else None)
            if count == 0:
                return "🛒 Keine offenen Einkaufsitems."
            return f"✅ {count} Einkaufsitem(s) abgehakt! Einkaufsliste geleert."

        # ─── Logging ──────────────────────────────────────────────────────────
        elif name == "log_workout":
            log = await log_workout(session, user.id, **args)
            d = log.data
            result = f"💪 Workout geloggt: {d.get('exercise')}"
            if d.get("weight"):
                result += f" {d['weight']}kg"
            if d.get("reps"):
                result += f" ×{d['reps']}"
                if d.get("sets") and d["sets"] > 1:
                    result += f" ×{d['sets']}Sätze"
            await _notify_achievements(session, user)
            return result

        elif name == "log_water":
            total = await log_water(session, user.id, args["amount_liters"])
            await _notify_achievements(session, user)
            return f"💧 {args['amount_liters']}L geloggt. Gesamt heute: {total:.1f}L"

        elif name == "log_mood":
            await log_mood(session, user.id, args["score"], args.get("notes", ""))
            score = args["score"]
            emoji = "😊" if score >= 7 else "😐" if score >= 4 else "😔"
            return f"{emoji} Mood {score}/10 gespeichert"

        elif name == "log_progress":
            log = await log_progress(
                session, user.id,
                args["key_result_id"],
                args["value"],
                args.get("increment", True),
                args.get("notes", ""),
            )
            await _notify_achievements(session, user)
            return f"📈 Fortschritt geloggt: {args['value']} für KR#{args['key_result_id']}"

        elif name == "log_food":
            log = await log_food(session, user.id, **args)
            return f"🍽️ Mahlzeit geloggt: {args['description']}"

        # ─── Routines ─────────────────────────────────────────────────────────
        elif name == "create_routine":
            routine = await create_routine(session, user.id, **args)
            return f"✅ Routine #{routine.id} erstellt: *{routine.title}* ({routine.frequency_human})"

        elif name == "complete_routine":
            comp = await complete_routine(session, user.id, args["routine_id"], args.get("notes"))
            if not comp:
                return f"Routine #{args['routine_id']} nicht gefunden."
            await _notify_achievements(session, user)
            return f"✅ Routine #{args['routine_id']} für heute erledigt!"

        # ─── Calendar ─────────────────────────────────────────────────────────
        elif name == "create_calendar_event":
            event = await create_calendar_event(session, user.id, **args)
            return (
                f"📅 Kalender-Event erstellt: *{event.title}*\n"
                f"   {event.start_time.strftime('%d.%m.%Y %H:%M')}"
            )

        # ─── Brain Dump ───────────────────────────────────────────────────────
        elif name == "store_brain_dump":
            bd = await create_brain_dump(session, user.id, args["content"], args.get("linked_objective_id"))
            await _notify_achievements(session, user)
            return f"🧠 Brain Dump #{bd.id} gespeichert. Wird später eingeordnet."

        # ─── Objective-Task Linking ───────────────────────────────────────────
        elif name == "suggest_tasks_for_objective":
            return await suggest_tasks_for_objective(
                session, user.id,
                args["objective_id"],
                args.get("tasks", []),
            )

        # ─── Query Tools ──────────────────────────────────────────────────────
        elif name == "get_todays_priorities":
            return await get_todays_priorities(session, user.id)

        elif name == "get_active_objectives":
            return await get_active_objectives(session, user.id)

        elif name == "get_progress_report":
            return await get_progress_report(session, user.id, args["objective_id"])

        elif name == "search_logs":
            return await search_logs(
                session, user.id,
                args["query"],
                args.get("log_type"),
                args.get("days_back", 30),
            )

        # ─── Day Planning ─────────────────────────────────────────────────────
        elif name == "plan_my_day":
            import re
            from datetime import date as date_cls
            from bot.core.calendar import create_calendar_event as _create_event, get_todays_events

            plan_date_str = args.get("date") or date_cls.today().isoformat()
            work_start = args.get("work_start", "08:00")
            work_end = args.get("work_end", "20:00")

            # Load context
            tasks = await get_open_tasks(session, user.id, limit=15)
            routines = await get_active_routines(session, user.id)
            completed_ids = await get_todays_completions(session, user.id)
            events = await get_todays_events(session, user.id)

            tasks_text = "\n".join(
                f"- [P{t.priority}] {t.title}" + (f" (fällig: {t.due_date})" if t.due_date else "")
                for t in tasks
            ) or "Keine offenen Tasks"

            routines_text = "\n".join(
                f"- {r.title}" + (" ✅ erledigt" if r.id in completed_ids else "")
                for r in routines
            ) or "Keine Routinen"

            events_text = "\n".join(
                f"- {e.start_time.strftime('%H:%M')}"
                + (f"–{e.end_time.strftime('%H:%M')}" if e.end_time else "")
                + f" {e.title}"
                for e in events
            ) or "Keine Termine"

            plan_prompt = (
                f"Erstelle einen JSON-Tagesplan für {plan_date_str} ({work_start}–{work_end}).\n\n"
                f"OFFENE TASKS (Priorität 1=hoch):\n{tasks_text}\n\n"
                f"ROUTINEN:\n{routines_text}\n\n"
                f"BESTEHENDE TERMINE (diese Zeiten freilassen!):\n{events_text}\n\n"
                "Erstelle einen JSON-Array mit Zeitblöcken:\n"
                '[{"title":"...","start":"HH:MM","end":"HH:MM","type":"work|training|routine|meeting|break","focus":"optionaler Fokus-Hinweis"}]\n\n'
                "Regeln:\n"
                "- Bestehende Termine NICHT überschreiben\n"
                "- Fokusblöcke 45–90 Min, dann 15 Min Pause\n"
                "- Höchstpriorität-Tasks zuerst planen\n"
                "- Mahlzeiten einplanen (Frühstück ~08:00, Mittag ~12:30, Abend ~18:30)\n"
                "- Nur JSON-Array zurückgeben, kein anderer Text"
            )

            plan_response = await openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": plan_prompt}],
                max_tokens=800,
                temperature=0.3,
            )
            raw = plan_response.choices[0].message.content or "[]"
            json_match = re.search(r"\[.*\]", raw, re.DOTALL)
            blocks: list[dict] = []
            if json_match:
                try:
                    blocks = json.loads(json_match.group())
                except Exception:
                    pass

            TYPE_MAP = {
                "work": "reminder", "training": "training", "routine": "routine",
                "meeting": "meeting", "break": "reminder", "deadline": "deadline",
            }
            EMOJI_MAP = {
                "training": "💪", "routine": "📋", "meeting": "🤝",
                "deadline": "🔴", "reminder": "⏰",
            }

            created = []
            for block in blocks:
                try:
                    ev = await _create_event(
                        session, user.id,
                        title=block["title"],
                        start_time=f"{plan_date_str} {block['start']}",
                        end_time=f"{plan_date_str} {block['end']}",
                        event_type=TYPE_MAP.get(block.get("type", "work"), "reminder"),
                        description=block.get("focus"),
                    )
                    created.append((ev, block.get("type", "work")))
                except Exception as e:
                    logger.warning("plan_my_day block failed: %s", e)

            lines = [f"📅 *Tagesplan {plan_date_str}* ({work_start}–{work_end})\n"]
            for ev, btype in created:
                emoji = EMOJI_MAP.get(ev.event_type, "⏰")
                time_str = ev.start_time.strftime("%H:%M")
                if ev.end_time:
                    time_str += f"–{ev.end_time.strftime('%H:%M')}"
                lines.append(f"{emoji} {time_str}  {ev.title}")
            lines.append(f"\n✅ {len(created)} Blöcke im Kalender gespeichert.")
            return "\n".join(lines)

        # ─── Fitness Splits ───────────────────────────────────────────────────
        elif name == "create_fitness_split":
            split = await create_fitness_split(session, user.id, **args)
            ex_preview = ", ".join(e.get("name", "?") for e in (split.exercises or [])[:3])
            if len(split.exercises or []) > 3:
                ex_preview += f" +{len(split.exercises) - 3}"
            return (
                f"✅ Split #{split.id} erstellt: *{split.name}*\n"
                f"   Übungen: {ex_preview}\n"
                f"→ split_id={split.id} für log_workout verwenden"
            )

        elif name == "get_fitness_plan":
            return await _get_fitness_plan(session, user.id)

        # ─── Shopping Defaults ────────────────────────────────────────────────
        elif name == "create_shopping_default":
            from sqlalchemy import select as sa_select
            existing = await session.execute(
                sa_select(ShoppingDefault).where(
                    ShoppingDefault.user_id == user.id,
                    ShoppingDefault.title == args["title"],
                )
            )
            if existing.scalar_one_or_none():
                return f"⭐ '{args['title']}' ist bereits ein Standard-Item."
            sd = ShoppingDefault(
                user_id=user.id,
                title=args["title"],
                category=args.get("category"),
                active=True,
            )
            session.add(sd)
            await session.flush()
            return f"⭐ Standard-Item #{sd.id} gespeichert: *{sd.title}*" + (f" [{sd.category}]" if sd.category else "")

        elif name == "load_shopping_defaults":
            from sqlalchemy import select as sa_select
            defaults_result = await session.execute(
                sa_select(ShoppingDefault).where(
                    ShoppingDefault.user_id == user.id,
                    ShoppingDefault.active == True,  # noqa: E712
                )
            )
            defaults = defaults_result.scalars().all()
            if not defaults:
                return "📋 Keine Standard-Items gespeichert. Nutze create_shopping_default um welche anzulegen."
            # Check which ones already on the list
            existing_result = await session.execute(
                sa_select(Task).where(
                    Task.user_id == user.id,
                    Task.category == "shopping",
                    Task.status.in_(["todo", "in_progress"]),
                )
            )
            existing_titles = {t.title.lower() for t in existing_result.scalars().all()}
            added = []
            for d in defaults:
                if d.title.lower() not in existing_titles:
                    task = Task(
                        user_id=user.id,
                        title=d.title,
                        category="shopping",
                        priority=3,
                    )
                    session.add(task)
                    added.append(d.title)
            await session.flush()
            if not added:
                return "🛒 Alle Standard-Items sind bereits auf der Einkaufsliste."
            return f"🛒 {len(added)} Standard-Items zur Einkaufsliste hinzugefügt:\n" + "\n".join(f"  ☐ {t}" for t in added)

        # ─── Settings ─────────────────────────────────────────────────────────
        elif name == "update_user_settings":
            key = args["setting_key"]
            raw_value = args["setting_value"]
            # Parse boolean values
            if raw_value.lower() in ("true", "false"):
                value = raw_value.lower() == "true"
            else:
                value = raw_value
            await update_setting(session, user.id, key, value)
            status = "✅ AN" if value is True else "❌ AUS" if value is False else str(value)
            return f"⚙️ Einstellung *{key}* → {status}"

        return f"Unbekanntes Tool: {name}"

    except Exception as e:
        logger.exception("Tool %s failed: %s", name, e)
        return f"Fehler beim Ausführen von {name}: {str(e)}"


async def process_message(
    session: AsyncSession,
    user: User,
    message: str,
    source: str = "text",
    image_url: Optional[str] = None,
) -> str:
    """
    Process a user message through GPT-4o with function calling.
    Supports multi-turn tool calling loop (max 5 iterations).
    Returns the assistant's text response.
    """
    context = await build_context(session, user)
    system = SYSTEM_PROMPT.format(context=context)

    # Load last 5 conversation pairs from today for chat history
    today = date.today()
    history_result = await session.execute(
        select(Conversation)
        .where(
            Conversation.user_id == user.id,
            Conversation.session_date == today,
            Conversation.role.in_(["user", "assistant"]),
        )
        .order_by(Conversation.id.desc())
        .limit(10)
    )
    history_rows = list(reversed(history_result.scalars().all()))

    # Build message payload
    if image_url:
        user_content: Any = [
            {"type": "text", "text": message},
            {"type": "image_url", "image_url": {"url": image_url}},
        ]
    else:
        user_content = message

    messages: list[dict] = [{"role": "system", "content": system}]
    for row in history_rows:
        messages.append({"role": row.role, "content": row.content})
    messages.append({"role": "user", "content": user_content})

    max_iterations = 5
    for iteration in range(max_iterations):
        response = await openai_client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
            max_tokens=1000,
            temperature=0.4,
        )

        msg = response.choices[0].message

        if not msg.tool_calls:
            reply = msg.content or ""
            break

        # Add assistant message with tool calls
        messages.append({
            "role": "assistant",
            "content": msg.content or "",
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
                for tc in msg.tool_calls
            ],
        })

        # Execute all tool calls
        for tc in msg.tool_calls:
            try:
                args = json.loads(tc.function.arguments)
            except json.JSONDecodeError:
                args = {}
            result = await _execute_tool(tc.function.name, args, session, user)
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result,
            })
    else:
        # Max iterations — get final response
        final = await openai_client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            max_tokens=800,
            temperature=0.4,
        )
        reply = final.choices[0].message.content or "Verarbeitung abgeschlossen."

    # Save conversation
    session.add(Conversation(
        user_id=user.id,
        role="user",
        content=message,
        extra_data={"source": source},
        session_date=today,
    ))
    session.add(Conversation(
        user_id=user.id,
        role="assistant",
        content=reply,
        extra_data={},
        session_date=today,
    ))

    return reply
