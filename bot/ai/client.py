"""OpenAI client — GPT-4o with function calling and next-action principle."""
import json
import logging
import re
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
    ExpansionGuardException,
    create_key_result,
    create_objective,
    create_objective_with_guard,
    get_active_objectives,
    get_progress_report,
    list_active_objectives,
    suggest_objective_to_cut,
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


# ─── V3 P03 — Coach-Modus softener detection ─────────────────────────────────
# Hits are logged only; the message is NOT rewritten. If hit count is high over
# time, the System Prompt needs more pressure (or the model drifted).
_SOFTENER_PATTERNS: list[re.Pattern] = [
    re.compile(r"\b(bitte|gerne|natürlich|nat[üu]rlich)\b", re.IGNORECASE),
    re.compile(r"\b(super|klasse|top|wunderbar|prima|spitze)\s*[!.]", re.IGNORECASE),
]


def detect_softeners(text: str) -> list[str]:
    """Return list of softener words found in `text`. Used by sanitizer + tests."""
    if not text:
        return []
    hits: list[str] = []
    for pat in _SOFTENER_PATTERNS:
        for m in pat.finditer(text):
            hits.append(m.group(0))
    return hits


def sanitize_reply(reply: str, *, user_id: Optional[int] = None) -> str:
    """Log-only sanitizer — never rewrites the message (Coach-Modus is a system-prompt
    contract, not a regex). Returns the original `reply` so callers can swap in-place."""
    hits = detect_softeners(reply)
    if hits:
        logger.warning(
            "AI used softeners (user=%s, count=%d): %s",
            user_id, len(hits), ", ".join(hits[:5]),
        )
    return reply


async def _notify_achievements(session: AsyncSession, user: User) -> None:
    """Check achievements and send Telegram notifications for newly unlocked ones."""
    try:
        from bot.telegram.sender import send_message
        from bot.core.gamification import add_xp
        newly_unlocked = await check_achievements(user.id, session)
        for achievement in newly_unlocked:
            await send_message(user.telegram_id, format_achievement_message(achievement))
            if achievement.xp_reward > 0:
                _, new_level, leveled_up, _ = await add_xp(
                    user.id, achievement.xp_reward, f"achievement_{achievement.key}", session
                )
                if leveled_up:
                    await send_message(
                        user.telegram_id,
                        f"⬆️ LEVEL UP! Du bist jetzt Level {new_level}! 🎉",
                    )
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
        # ─── V3 P03 — Expansion Protection: list active objectives ──────────
        if name == "list_active_objectives":
            data = await list_active_objectives(session, user.id)
            return json.dumps(data, ensure_ascii=False)

        # ─── Goal Onboarding ─────────────────────────────────────────────────
        if name == "start_goal_onboarding":
            from bot.core.goal_onboarding import get_active_onboarding, start_onboarding
            existing = await get_active_onboarding(session, user.id)
            if existing:
                return (
                    "Es läuft bereits ein Ziel-Onboarding. "
                    "Der Nutzer muss es erst abschließen oder mit /goal cancel abbrechen."
                )
            onboarding, intro = await start_onboarding(
                session, user.id, args["goal_text"]
            )
            return intro

        # ─── OKR ──────────────────────────────────────────────────────────────
        elif name == "create_objective":
            # V3 P08 — gate behind the expansion guard.
            try:
                result = await create_objective_with_guard(session, user.id, **args)
            except ExpansionGuardException as e:
                # Tell the user (via AI) exactly what's blocking + suggest a cut.
                cut = await suggest_objective_to_cut(session, user.id)
                cut_hint = ""
                if cut:
                    cut_hint = (
                        f"\nSchwächstes aktives Ziel: '{cut['title']}' "
                        f"({cut['days_stale']}d ohne Log, {int(cut['completion']*100)}% erfüllt). "
                        f"`/cut {cut['id']}` um es zu pausieren."
                    )
                return f"⛔ {e}{cut_hint}"
            obj = result["objective"]
            await _notify_achievements(session, user)
            response = (
                f"✅ Objective #{obj.id} erstellt: *{obj.title}* [{obj.category}]\n"
                f"→ Jetzt suggest_tasks_for_objective aufrufen um konkrete Tasks zu erstellen."
            )
            if result.get("warning"):
                response = f"⚠️ {result['warning']}\n\n{response}"
            return response

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

            # Auto-update Trainingsplan document
            try:
                from bot.core.smart_detector import _get_or_create_document, _append_to_document
                tp_doc = await _get_or_create_document(session, user.id, "Trainingsplan", "🏋️")
                entry_parts = [d.get("exercise", "?")]
                if d.get("weight"):
                    entry_parts.append(f"{d['weight']}kg")
                if d.get("sets") and d.get("reps"):
                    entry_parts.append(f"{d['sets']}×{d['reps']}")
                if d.get("duration_minutes"):
                    entry_parts.append(f"{d['duration_minutes']}min")
                if d.get("notes"):
                    entry_parts.append(f"({d['notes']})")
                await _append_to_document(tp_doc, " ".join(entry_parts), "workout")
            except Exception as _e:
                logger.debug("Trainingsplan doc update failed: %s", _e)

            # Suggest progressive overload based on previous session
            try:
                from bot.database.models import Log as _Log
                _prev_logs = (await session.execute(
                    select(_Log).where(and_(
                        _Log.user_id == user.id,
                        _Log.log_type == "workout",
                        _Log.id != log.id,
                    )).order_by(_Log.logged_at.desc()).limit(50)
                )).scalars().all()
                _ex_lower = d.get("exercise", "").lower()
                for _pl in _prev_logs:
                    if _ex_lower in (_pl.data.get("exercise") or "").lower():
                        _pw = _pl.data.get("weight")
                        _pr = _pl.data.get("reps")
                        _ps = _pl.data.get("sets")
                        if _pw:
                            _next_w = round(_pw + 2.5, 1)
                            _cur_w = d.get("weight")
                            if _cur_w and _cur_w >= _pw:
                                result += f"\n📈 Letztes Mal: {_pw}kg → Nächstes Mal: {_next_w}kg probieren"
                            else:
                                result += f"\n💡 Referenz: {_pl.logged_at.strftime('%d.%m')}: {_pw}kg × {_ps or '?'}×{_pr or '?'}"
                        break
            except Exception as _e:
                logger.debug("Progression suggestion failed: %s", _e)

            return result

        elif name == "log_water":
            total = await log_water(session, user.id, args["amount_liters"])
            await _notify_achievements(session, user)
            result = f"💧 {args['amount_liters']}L geloggt. Gesamt heute: {total:.1f}L"

            # Auto-check: if daily water total meets streak KR target → increment streak (once per day)
            from datetime import date as _date
            from bot.database.models import KeyResult as _KR, Log as _Log
            _today_start = datetime.combine(_date.today(), datetime.min.time())
            _water_krs = (await session.execute(
                select(_KR).where(and_(
                    _KR.user_id == user.id,
                    _KR.status == "active",
                    _KR.metric_type == "streak",
                ))
            )).scalars().all()
            for _kr in _water_krs:
                if "wasser" not in _kr.title.lower() and "water" not in _kr.title.lower():
                    continue
                if _kr.target_value and total < _kr.target_value:
                    continue  # day goal not met yet
                # Check: not already updated today
                _already = (await session.execute(
                    select(_Log).where(and_(
                        _Log.user_id == user.id,
                        _Log.log_type == "progress",
                        _Log.key_result_id == _kr.id,
                        _Log.logged_at >= _today_start,
                    ))
                )).scalar_one_or_none()
                if _already:
                    continue
                _kr.current_value = (_kr.current_value or 0) + 1
                if _kr.target_value and _kr.current_value >= _kr.target_value:
                    _kr.status = "completed"
                await session.flush()
                result += f"\n🎯 Tagesziel {_kr.target_value}L erreicht! {_kr.title}: {int(_kr.current_value)}/{int(_kr.target_value or 0)} Tage ✅"
            return result

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
            routine_id = args["routine_id"]
            # Load routine before completing to get linked KR info
            from bot.database.models import Routine as RoutineModel
            routine_obj = (await session.execute(
                select(RoutineModel).where(RoutineModel.id == routine_id)
            )).scalar_one_or_none()

            comp = await complete_routine(session, user.id, routine_id, args.get("notes"))
            if not comp:
                return f"Routine #{routine_id} nicht gefunden."
            await _notify_achievements(session, user)

            result = f"✅ *{routine_obj.title if routine_obj else f'Routine #{routine_id}'}* erledigt!"
            if routine_obj and routine_obj.linked_key_result_id:
                from bot.database.models import KeyResult as KRModel
                kr = (await session.execute(
                    select(KRModel).where(KRModel.id == routine_obj.linked_key_result_id)
                )).scalar_one_or_none()
                if kr:
                    bar = ""
                    if kr.target_value and kr.target_value > 0:
                        pct = min(100, int((kr.current_value / kr.target_value) * 100))
                        filled = pct // 10
                        bar = f" [{('█' * filled) + ('░' * (10 - filled))}] {pct}%"
                    completed_flag = " 🎉 Ziel erreicht!" if kr.status == "completed" else ""
                    result += f"\n📈 {kr.title}: {int(kr.current_value)}/{int(kr.target_value or 0)}{bar}{completed_flag}"
                    result += f"\n   ↳ KR#{kr.id} wurde automatisch aktualisiert — kein log_progress nötig"
            return result

        # ─── Calendar ─────────────────────────────────────────────────────────
        elif name == "create_calendar_event":
            event = await create_calendar_event(session, user.id, **args)
            return (
                f"📅 Kalender-Event erstellt: *{event.title}*\n"
                f"   {event.start_time.strftime('%d.%m.%Y %H:%M')}"
            )

        # ─── Contact ──────────────────────────────────────────────────────────
        elif name == "create_contact":
            from bot.core.relationships import create_contact as _create_contact
            from datetime import date as _date
            birthday_raw = args.pop("birthday", None)
            birthday = None
            if birthday_raw:
                try:
                    birthday = _date.fromisoformat(birthday_raw)
                except ValueError:
                    pass
            contact, created = await _create_contact(session, user.id, birthday=birthday, **args)
            if created:
                return f"👤 Kontakt angelegt: *{contact.name}*" + (f"\n   📝 {contact.notes}" if contact.notes else "")
            else:
                return f"👤 Kontakt bereits vorhanden: *{contact.name}* (aktualisiert)"

        # ─── Document Store ───────────────────────────────────────────────────
        elif name == "store_document_entry":
            from bot.core.smart_detector import (
                _get_or_create_document,
                _append_to_document,
                _update_kr_streak,
            )
            doc_name = args["document"]
            content = args["content"]

            # Determine emoji based on document type
            emoji_map = {"tagebuch": "📓", "dankbarkeit": "🙏"}
            emoji = emoji_map.get(doc_name.lower(), "📄")

            doc = await _get_or_create_document(session, user.id, doc_name, emoji)
            await _append_to_document(doc, content, doc_name.lower())

            # Update matching KR streak based on document type
            kr_keywords_map = {
                "tagebuch": ["journal", "tagebuch"],
                "dankbarkeit": ["dankbar", "gratitude"],
            }
            kr_keywords = kr_keywords_map.get(doc_name.lower(), [doc_name.lower()])
            kr = await _update_kr_streak(session, user.id, kr_keywords)

            xp_map = {"tagebuch": 5, "dankbarkeit": 3}
            xp = xp_map.get(doc_name.lower(), 3)
            user.xp = (user.xp or 0) + xp

            kr_msg = ""
            if kr:
                kr_msg = f"\n📈 {kr.title}: {int(kr.current_value)}/{int(kr.target_value or 0)}"
                if kr.status == "completed":
                    kr_msg += " 🎉 Ziel erreicht!"

            return (
                f"{emoji} *{doc_name}* gespeichert! +{xp} XP{kr_msg}\n"
                f"_{content[:100]}{'...' if len(content) > 100 else ''}_"
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
                f"- [Routine#{r.id}, {r.time_of_day}] {r.title}"
                + (" ✅ erledigt" if r.id in completed_ids else "")
                + (f" → KR#{r.linked_key_result_id}" if r.linked_key_result_id else "")
                for r in routines
            ) or "Keine Routinen"

            events_text = "\n".join(
                f"- {e.start_time.strftime('%H:%M')}"
                + (f"–{e.end_time.strftime('%H:%M')}" if e.end_time else "")
                + f" {e.title}"
                for e in events
            ) or "Keine Termine"

            # Load fitness split for today
            fitness_info = ""
            try:
                from bot.core.fitness_protocol import get_today_split, load_fitness_protocol
                fv = get_today_split(load_fitness_protocol(), date_cls.fromisoformat(plan_date_str))
                if fv.get("is_rest_day"):
                    fitness_info = "\nFITNESS HEUTE: Ruhetag"
                else:
                    exs = ", ".join(fv.get("exercises", [])[:4])
                    fitness_info = (
                        f"\nFITNESS HEUTE: {fv.get('split_name')} ({fv.get('focus', '')})"
                        f"\n→ Trainingsblock Titel: '💪 {fv.get('split_name')}: {exs}'"
                    )
            except Exception:
                pass

            plan_prompt = (
                f"Erstelle einen JSON-Tagesplan für {plan_date_str} ({work_start}–{work_end}).\n\n"
                f"OFFENE TASKS (Priorität 1=hoch):\n{tasks_text}\n\n"
                f"ROUTINEN (mit IDs und Tageszeit):\n{routines_text}\n\n"
                f"BESTEHENDE TERMINE (diese Zeiten freilassen!):\n{events_text}"
                f"{fitness_info}\n\n"
                "Erstelle einen JSON-Array mit Zeitblöcken:\n"
                '[{"title":"...","start":"HH:MM","end":"HH:MM","type":"work|training|routine|meeting|break","focus":"optionaler Fokus-Hinweis"}]\n\n'
                "Regeln:\n"
                "- Bestehende Termine NICHT überschreiben\n"
                "- Fokusblöcke 45–90 Min, dann 15 Min Pause\n"
                "- Höchstpriorität-Tasks zuerst planen\n"
                "- Mahlzeiten einplanen (Frühstück ~08:00, Mittag ~12:30, Abend ~18:30)\n"
                "- Routine-Blöcke: exakten Routine-Titel verwenden (z.B. 'Morgendliche Meditation')\n"
                "- Training: vollständigen Split-Titel mit Top-3-Übungen verwenden (s.o.)\n"
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

        # ─── Finance ──────────────────────────────────────────────────────────
        elif name == "log_expense":
            from bot.core.finance import log_expense as _log_expense
            tx_date = None
            if args.get("date"):
                from datetime import date as _date
                try:
                    tx_date = _date.fromisoformat(args["date"])
                except ValueError:
                    pass
            result = await _log_expense(
                session,
                user.id,
                amount=float(args["amount"]),
                category=args.get("category", "sonstiges"),
                description=args["description"],
                transaction_date=tx_date,
                is_recurring=args.get("is_recurring", False),
            )
            lines = [f"💸 Ausgabe geloggt: {result['amount']:.2f}€ [{result['category']}] — {result['description']}"]
            if result.get("budget_status"):
                lines.append(f"📊 Budget {result['category']}: {result['budget_status']}")
            if result.get("budget_warning"):
                lines.append(result["budget_warning"])
            return "\n".join(lines)

        elif name == "log_income":
            from bot.core.finance import log_income as _log_income
            tx_date = None
            if args.get("date"):
                from datetime import date as _date
                try:
                    tx_date = _date.fromisoformat(args["date"])
                except ValueError:
                    pass
            result = await _log_income(
                session,
                user.id,
                amount=float(args["amount"]),
                source=args["source"],
                transaction_date=tx_date,
            )
            return f"💰 Einnahme geloggt: {result['amount']:.2f}€ — {result['source']}"

        elif name == "get_financial_summary":
            from bot.core.finance import get_financial_summary as _get_fin
            summary = await _get_fin(session, user.id)
            if summary["total_income"] == 0 and summary["total_expenses"] == 0:
                return "Noch keine Finanzdaten für diesen Monat. Starte mit 'Kaffee 3€' oder 'Gehalt 2800€'."
            lines = [f"📊 Finanzen {summary['month']}:"]
            lines.append(f"  Einnahmen: {summary['total_income']:.0f}€")
            lines.append(f"  Ausgaben: {summary['total_expenses']:.0f}€")
            lines.append(f"  Balance: {summary['balance']:+.0f}€")
            if summary["total_income"] > 0:
                lines.append(f"  Sparquote: {summary['savings_rate']:.0f}%")
            if summary["category_lines"]:
                lines.append("  Kategorien:")
                lines.extend(f"    {l}" for l in summary["category_lines"])
            return "\n".join(lines)

        elif name == "set_monthly_budget":
            from bot.core.finance import set_budget as _set_budget
            result = await _set_budget(
                session,
                user.id,
                category=args["category"],
                monthly_limit=float(args["monthly_limit"]),
            )
            action = "aktualisiert" if result.get("updated") else "erstellt"
            return f"✅ Budget {action}: {result['category']} = {result['monthly_limit']:.0f}€/Monat"

        # ─── Health Tracking ──────────────────────────────────────────────────
        elif name == "log_sleep":
            from bot.core.health_sync import sync_health_metrics
            tx_date = args.get("date")
            result = await sync_health_metrics(session, user, {
                "sleep_hours": float(args["hours"]),
                "sleep_quality": args.get("quality"),
                "metric_date": tx_date,
            }, source="telegram")
            hours = float(args["hours"])
            emoji = "✅" if hours >= 7 else "⚠️"
            quality_str = f" (Qualität: {args['quality']}/10)" if args.get("quality") else ""
            kr_str = f"\n{result['kr_updates'][0]}" if result.get("kr_updates") else ""
            return f"{emoji} Schlaf geloggt: {hours:.1f}h{quality_str}{kr_str}"

        elif name == "log_steps":
            from bot.core.health_sync import sync_health_metrics
            steps = int(args["count"])
            result = await sync_health_metrics(session, user, {
                "steps": steps,
                "metric_date": args.get("date"),
            }, source="telegram")
            emoji = "✅" if steps >= 8000 else "🚶"
            kr_str = f"\n{result['kr_updates'][0]}" if result.get("kr_updates") else ""
            return f"{emoji} Schritte geloggt: {steps:,}{kr_str}"

        elif name == "log_hrv":
            from bot.core.health_sync import sync_health_metrics
            hrv = int(args["score"])
            await sync_health_metrics(session, user, {
                "hrv": hrv,
                "metric_date": args.get("date"),
            }, source="telegram")
            quality = "sehr gut" if hrv > 60 else "gut" if hrv > 45 else "mittel" if hrv > 30 else "niedrig"
            return f"💓 HRV geloggt: {hrv}ms ({quality})"

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

    # V3 P03 — log softener usage (does not rewrite reply)
    sanitize_reply(reply, user_id=user.id)

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
