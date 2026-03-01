"""OpenAI client — processes messages with function calling."""
import json
import logging
from datetime import date, datetime
from typing import Any, Optional

from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession

from bot.ai.context import build_context
from bot.ai.prompts import SYSTEM_PROMPT
from bot.ai.tools import TOOLS
from bot.config import settings
from bot.core.brain_dumps import create_brain_dump
from bot.core.calendar import create_calendar_event
from bot.core.logs import log_mood, log_progress, log_water, log_workout
from bot.core.objectives import create_key_result, create_objective, get_active_objectives, get_progress_report
from bot.core.priorities import get_todays_priorities
from bot.core.routines import complete_routine, create_routine
from bot.core.tasks import (
    complete_task,
    create_task,
    search_logs,
    update_task_status,
)
from bot.database.models import Conversation, User

logger = logging.getLogger(__name__)

openai_client = AsyncOpenAI(api_key=settings.openai_api_key)


async def _execute_tool(
    name: str,
    args: dict[str, Any],
    session: AsyncSession,
    user: User,
) -> str:
    """Execute a tool call and return a string result."""
    try:
        if name == "create_objective":
            obj = await create_objective(session, user.id, **args)
            return f"Objective #{obj.id} erstellt: {obj.title}"

        elif name == "create_key_result":
            kr = await create_key_result(session, user.id, **args)
            return f"Key Result #{kr.id} erstellt: {kr.title}"

        elif name == "create_task":
            task = await create_task(session, user.id, **args)
            return f"Task #{task.id} erstellt: {task.title}"

        elif name == "complete_task":
            task = await complete_task(session, user.id, args["task_id"])
            if task:
                return f"Task #{task.id} '{task.title}' als erledigt markiert ✅"
            return f"Task #{args['task_id']} nicht gefunden"

        elif name == "update_task_status":
            task = await update_task_status(session, user.id, args["task_id"], args["status"])
            if task:
                return f"Task #{task.id} Status → {args['status']}"
            return f"Task #{args['task_id']} nicht gefunden"

        elif name == "log_workout":
            log = await log_workout(session, user.id, **args)
            d = log.data
            result = f"Workout geloggt: {d.get('exercise')}"
            if d.get("weight"):
                result += f" {d['weight']}kg"
            if d.get("reps") and d.get("sets"):
                result += f" ×{d['reps']}×{d['sets']}Sätze"
            return result

        elif name == "log_water":
            total = await log_water(session, user.id, args["amount_liters"])
            return f"💧 {args['amount_liters']}L geloggt. Gesamt heute: {total:.1f}L"

        elif name == "log_mood":
            await log_mood(session, user.id, args["score"], args.get("notes", ""))
            return f"Mood {args['score']}/10 gespeichert"

        elif name == "log_progress":
            log = await log_progress(session, user.id, args["key_result_id"], args["value"], args.get("notes", ""))
            return f"Fortschritt geloggt: +{args['value']} für KR#{args['key_result_id']}"

        elif name == "create_routine":
            routine = await create_routine(session, user.id, **args)
            return f"Routine #{routine.id} erstellt: {routine.title} ({routine.frequency_human})"

        elif name == "complete_routine":
            comp = await complete_routine(session, user.id, args["routine_id"], args.get("notes"))
            if comp:
                return f"Routine #{args['routine_id']} für heute erledigt ✅"
            return f"Routine #{args['routine_id']} nicht gefunden"

        elif name == "create_calendar_event":
            event = await create_calendar_event(session, user.id, **args)
            return f"Kalender-Event erstellt: {event.title} am {event.start_time.strftime('%d.%m.%Y %H:%M')}"

        elif name == "store_brain_dump":
            bd = await create_brain_dump(session, user.id, args["content"], args.get("linked_objective_id"))
            return f"🧠 Brain Dump #{bd.id} gespeichert"

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
    Returns the assistant's text response.
    """
    # Build context
    context = await build_context(session, user)
    system = SYSTEM_PROMPT.format(context=context)

    # Build message payload
    if image_url:
        user_content: Any = [
            {"type": "text", "text": message},
            {"type": "image_url", "image_url": {"url": image_url}},
        ]
    else:
        user_content = message

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user_content},
    ]

    # Call OpenAI with tools
    response = await openai_client.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        tools=TOOLS,
        tool_choice="auto",
        max_tokens=1000,
        temperature=0.4,
    )

    msg = response.choices[0].message
    tool_results: list[str] = []

    # Handle tool calls
    if msg.tool_calls:
        messages.append({"role": "assistant", "content": msg.content or "", "tool_calls": [
            {
                "id": tc.id,
                "type": "function",
                "function": {"name": tc.function.name, "arguments": tc.function.arguments},
            }
            for tc in msg.tool_calls
        ]})

        for tc in msg.tool_calls:
            try:
                args = json.loads(tc.function.arguments)
            except json.JSONDecodeError:
                args = {}
            result = await _execute_tool(tc.function.name, args, session, user)
            tool_results.append(result)
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result,
            })

        # Get final response after tool calls
        final_response = await openai_client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            max_tokens=800,
            temperature=0.4,
        )
        reply = final_response.choices[0].message.content or ""
    else:
        reply = msg.content or ""

    # Save conversation
    today = date.today()
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
        extra_data={"tool_calls": len(msg.tool_calls) if msg.tool_calls else 0},
        session_date=today,
    ))

    return reply
