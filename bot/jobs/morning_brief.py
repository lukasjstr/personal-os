"""Phase 4 / Epic 2.3: Morning brief — upgraded with free-slot planning, blockers, stale objectives."""
import logging
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from openai import AsyncOpenAI
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import settings
from bot.core.fitness_protocol import get_today_split, load_fitness_protocol
from bot.core.free_slot_planner import plan_free_slots
from bot.core.gamification import get_level_title
from bot.core.supplement_protocol import generate_daily_checklist, load_protocol
from bot.database.connection import get_session
from bot.database.models import (
    CalendarEvent, DailyBrief, EveningCheckin, KeyResult, Log, Objective, Routine,
    RoutineCompletion, Task, User, UserInsight,
)
from bot.jobs.daily_suggestions import get_or_generate_suggestions
from bot.telegram.sender import send_message

logger = logging.getLogger(__name__)
openai_client = AsyncOpenAI(api_key=settings.openai_api_key)

_STALE_OBJECTIVE_DAYS = 14  # flag objectives not updated in this many days


async def send_morning_brief() -> None:
    """Check all active users and send morning brief if their configured time matches now."""
    now_berlin = datetime.now(tz=ZoneInfo("Europe/Berlin"))
    current_time = now_berlin.strftime("%H:%M")
    today = now_berlin.date()

    async with get_session() as session:
        result = await session.execute(
            select(User).where(User.is_active == True)  # noqa: E712
        )
        users = result.scalars().all()

        for user in users:
            s = user.settings or {}
            if not s.get("priorities_enabled", True):
                continue

            brief_time = s.get("morning_brief_time", "06:30")
            if current_time != brief_time:
                continue

            brief = await _get_or_create_daily_brief(session, user.id, today)
            if brief.brief_sent_at:
                continue

            try:
                text, priorities_snapshot = await _generate_brief_for_user(
                    session, user, today, now_berlin
                )
                success = await send_message(user.telegram_id, text)
                if success:
                    brief.brief_sent_at = datetime.utcnow()
                    brief.priorities = priorities_snapshot
                    await session.flush()
                    logger.info("Morning brief sent to user %s", user.id)

                    # Kick off morning context collection if not yet done today
                    try:
                        from bot.core.daily_intelligence import collect_morning_context
                        from bot.telegram.sender import get_bot
                        await collect_morning_context(get_bot(), user, session)
                    except Exception:
                        logger.exception(
                            "Morning context collection failed after brief for user %s", user.id
                        )
            except Exception:
                logger.exception("Failed to send morning brief to user %s", user.id)


async def _generate_brief_for_user(
    session: AsyncSession, user: User, today: date, now_berlin: datetime
) -> tuple[str, list]:
    """Generate the V3 Festnagel-Modus morning brief — deterministic template.

    Header sections (always shown when data present):
        ━━ STATUS ━━
        ━━ HEUTE — 3 MUSS ━━
        ━━ FESTNAGEL ━━
        ━━ KALENDER ━━
        ━━ AUSBLICK ━━

    Appended (preserved from pre-P05): Supplement + Fitness + AI-suggestions
    blocks for the Telegram message, since Lukas relies on these daily.

    Returns (message_text, priorities_snapshot).
    """
    today_start = datetime.combine(today, datetime.min.time())
    today_end = datetime.combine(today, datetime.max.time())

    # --- Open tasks (top priorities) ---
    task_result = await session.execute(
        select(Task).where(and_(
            Task.user_id == user.id,
            Task.status.in_(["todo", "in_progress"]),
            Task.category != "shopping",
        )).order_by(Task.priority.asc(), Task.due_date.asc().nulls_last()).limit(5)
    )
    tasks = task_result.scalars().all()

    # --- Morning routines ---
    routine_result = await session.execute(
        select(Routine).where(and_(
            Routine.user_id == user.id,
            Routine.status == "active",
            Routine.time_of_day.in_(["morning", "anytime"]),
        )).order_by(Routine.sort_order.asc(), Routine.id.asc())
    )
    routines = routine_result.scalars().all()

    # Auto-generate top-5 (autopilot)
    from bot.core.autopilot_planner import generate_top5, format_top5_for_telegram
    try:
        top5 = await generate_top5(session, user, today)
    except Exception:
        top5 = []

    # --- Calendar events today ---
    cal_result = await session.execute(
        select(CalendarEvent).where(and_(
            CalendarEvent.user_id == user.id,
            CalendarEvent.start_time >= today_start,
            CalendarEvent.start_time <= today_end,
        )).order_by(CalendarEvent.start_time)
    )
    events = cal_result.scalars().all()

    # Load today's auto-scheduled work blocks (from day scheduler)
    work_blocks_res = await session.execute(
        select(CalendarEvent).where(and_(
            CalendarEvent.user_id == user.id,
            CalendarEvent.start_time >= today_start,
            CalendarEvent.start_time <= today_end,
            CalendarEvent.event_type == "work_block",
        )).order_by(CalendarEvent.start_time)
    )
    work_blocks = work_blocks_res.scalars().all()

    # --- Overdue tasks ---
    overdue_result = await session.execute(
        select(Task).where(and_(
            Task.user_id == user.id,
            Task.status.in_(["todo", "in_progress"]),
            Task.due_date < today,
            Task.category != "shopping",
        ))
    )
    overdue = overdue_result.scalars().all()

    # --- Blocked tasks (Epic 2.3) ---
    blocked_result = await session.execute(
        select(Task).where(and_(
            Task.user_id == user.id,
            Task.status.in_(["todo", "in_progress"]),
            Task.blocked_by_task_id.isnot(None),
            Task.category != "shopping",
        )).limit(5)
    )
    blocked_tasks = blocked_result.scalars().all()

    # --- Stale objectives (Epic 2.3) ---
    stale_cutoff = datetime.combine(
        today - timedelta(days=_STALE_OBJECTIVE_DAYS), datetime.min.time()
    )
    stale_result = await session.execute(
        select(Objective).where(and_(
            Objective.user_id == user.id,
            Objective.status == "active",
            or_(
                Objective.updated_at < stale_cutoff,
                and_(Objective.updated_at.is_(None), Objective.created_at < stale_cutoff),
            ),
        )).order_by(Objective.updated_at.asc().nulls_first()).limit(3)
    )
    stale_objectives = stale_result.scalars().all()

    # --- Free-slot plan (Epic 2.3, reuses Epic 2.2 planner) ---
    slot_plan = plan_free_slots(events=events, tasks=tasks, today=today, now_dt=now_berlin)
    suggested_blocks = slot_plan.get("suggested_blocks", [])[:2]

    # --- Yesterday's mood ---
    yesterday_start = datetime.combine(today - timedelta(days=1), datetime.min.time())
    mood_result = await session.execute(
        select(Log).where(and_(
            Log.user_id == user.id,
            Log.log_type == "mood",
            Log.logged_at >= yesterday_start,
            Log.logged_at < today_start,
        )).order_by(Log.logged_at.desc()).limit(1)
    )
    yesterday_mood = mood_result.scalar_one_or_none()

    # --- Smart Brief: Training Skip Tracker (last 7 days) ---
    week_ago = datetime.combine(today - timedelta(days=7), datetime.min.time())
    training_keywords = ["sport", "training", "gym", "workout", "fitness", "lauf", "run"]

    # Check routines that are fitness-related and were NOT completed in last 7 days
    fitness_routines_res = await session.execute(
        select(Routine).where(and_(
            Routine.user_id == user.id,
            Routine.status == "active",
        ))
    )
    all_routines = fitness_routines_res.scalars().all()
    fitness_routine_ids = [
        r.id for r in all_routines
        if any(kw in r.title.lower() for kw in training_keywords)
    ]

    training_skip_count = 0
    if fitness_routine_ids:
        completions_res = await session.execute(
            select(RoutineCompletion).where(and_(
                RoutineCompletion.user_id == user.id,
                RoutineCompletion.routine_id.in_(fitness_routine_ids),
                RoutineCompletion.completed_at >= week_ago,
            ))
        )
        completions_this_week = completions_res.scalars().all()
        completed_days = len(set(c.completed_at.date() for c in completions_this_week))
        # Assume 5 weekdays of potential training
        training_skip_count = max(0, min(7, 5 - completed_days))

    # --- Smart Brief: Yesterday's evening energy score ---
    yesterday_energy = None
    yesterday_checkin_res = await session.execute(
        select(EveningCheckin).where(and_(
            EveningCheckin.user_id == user.id,
            EveningCheckin.date == today - timedelta(days=1),
        ))
    )
    yesterday_checkin = yesterday_checkin_res.scalar_one_or_none()
    if yesterday_checkin and yesterday_checkin.gap_analysis:
        yesterday_energy = yesterday_checkin.gap_analysis.get("energy_score")

    # --- Smart Brief: Pattern Insight of the Day ---
    pattern_insight = None
    try:
        insight_res = await session.execute(
            select(UserInsight).where(and_(
                UserInsight.user_id == user.id,
                UserInsight.is_active == True,  # noqa: E712
            )).order_by(UserInsight.created_at.desc()).limit(10)
        )
        insights = insight_res.scalars().all()
        if insights:
            import random
            pattern_insight = random.choice(insights)
    except Exception:
        pass

    # ── Build context string ───────────────────────────────────────────────────
    context_lines = []

    if tasks:
        context_lines.append("OFFENE TASKS (nach Priorität):")
        for t in tasks:
            due = f" [fällig: {t.due_date}]" if t.due_date else ""
            overdue_flag = " ⚠️ ÜBERFÄLLIG" if t.due_date and t.due_date < today else ""
            context_lines.append(f"  P{t.priority}: {t.title}{due}{overdue_flag}")

    if top5:
        context_lines.append("\nAUTOPILOT TOP-5 FÜR HEUTE (bereits ausgewählt):")
        for i, t in enumerate(top5, 1):
            context_lines.append(f"  {i}. P{t['priority']}: {t['title']} ({t['reason']})")

    if blocked_tasks:
        context_lines.append("\nBLOCKIERT (warten auf Abhängigkeiten):")
        for t in blocked_tasks[:3]:
            context_lines.append(f"  🔒 {t.title}")

    if stale_objectives:
        context_lines.append(f"\nSTAGNIEREND (>{_STALE_OBJECTIVE_DAYS} Tage keine Aktivität):")
        for obj in stale_objectives:
            last = obj.updated_at.strftime("%d.%m") if obj.updated_at else "unbekannt"
            context_lines.append(f"  📊 {obj.title} (zuletzt: {last})")

    if suggested_blocks:
        context_lines.append("\nFREIE SLOTS HEUTE (Empfehlung):")
        for b in suggested_blocks:
            start = b.get("start_time", "—")
            end = b.get("end_time", "—")
            title = b.get("task_title") or "offener Task"
            conf = b.get("confidence", "?")
            reason = b.get("task_reason", "")
            if start != "—":
                slot_line = f"  ⏱ {start}–{end}: {title}"
                if reason:
                    slot_line += f" ({reason})"
                context_lines.append(slot_line)

    if routines:
        context_lines.append("\nMORGEN-ROUTINEN:")
        for r in routines:
            context_lines.append(f"  ☐ {r.title}")

    supplement_view = None
    try:
        protocol = load_protocol()
        supplement_view = generate_daily_checklist(protocol, today)
        morning_count = len(supplement_view["slot_checklist"]["morning"])
        midday_count = len(supplement_view["slot_checklist"]["midday"])
        evening_count = len(supplement_view["slot_checklist"]["evening"])
        context_lines.append(
            "\nSUPPLEMENT-PROTOKOLL (heute aktiv): "
            f"Morgen {morning_count} · Mittag {midday_count} · Abend {evening_count}"
        )
    except Exception:
        logger.exception("Supplement protocol unavailable; continuing without it")

    fitness_view = None
    try:
        fitness_view = get_today_split(load_fitness_protocol(), today)
        if fitness_view.get("is_rest_day"):
            context_lines.append("\nFITNESS HEUTE: Rest / aktive Regeneration")
        else:
            context_lines.append(
                f"\nFITNESS HEUTE: {fitness_view.get('split_name')} ({fitness_view.get('focus', '')})"
            )
    except Exception:
        logger.exception("Fitness protocol unavailable; continuing without it")

    if events:
        context_lines.append("\nTERMINE HEUTE:")
        for e in events:
            time_str = e.start_time.strftime("%H:%M") if not e.all_day else "ganztägig"
            context_lines.append(f"  {time_str}: {e.title}")

    if work_blocks:
        context_lines.append("\nAUTOMATISCH GEPLANTE BLÖCKE HEUTE:")
        for b in work_blocks[:8]:
            time_str = b.start_time.strftime("%H:%M")
            end_str = b.end_time.strftime("%H:%M") if b.end_time else "?"
            context_lines.append(f"  ⏱ {time_str}–{end_str}: {b.title}")

    if overdue:
        context_lines.append(f"\nÜBERFÄLLIGE TASKS: {len(overdue)}")
        for t in overdue[:3]:
            context_lines.append(f"  ⚠️ {t.title} (fällig: {t.due_date})")

    if yesterday_mood:
        context_lines.append(f"\nGESTRIGE STIMMUNG: {yesterday_mood.data.get('score', '?')}/10")

    # Smart Brief enhancements
    if training_skip_count >= 2:
        context_lines.append(
            f"\n⚠️ TRAINING-WARNUNG: Bereits {training_skip_count}x Training diese Woche übersprungen — heute ist kritisch!"
        )

    if yesterday_energy is not None:
        try:
            energy_val = int(yesterday_energy)
            if energy_val <= 4:
                context_lines.append(
                    f"\n🔋 ENERGIE GESTERN NIEDRIG: {energy_val}/10 — heute leichte, erreichbare Tasks priorisieren!"
                )
        except (TypeError, ValueError):
            pass

    if pattern_insight:
        context_lines.append(
            f"\n💡 ERKENNTNIS DES TAGES: {pattern_insight.title} — {pattern_insight.description[:200]}"
        )

    total_xp = user.xp or 0
    level = user.level or 0
    level_title = get_level_title(level)
    context_lines.append(f"\nXP-STATUS: Level {level} ({level_title}) · {total_xp} XP gesamt")

    # ── V3 P05 Festnagel template — deterministic, no GPT-4o for the core brief ─
    from bot.core.festnagel import (
        generate_brief_status,
        generate_dropout_outlook,
        generate_festnagel,
        generate_three_musts,
    )

    status = await generate_brief_status(session, user.id, today)
    musts = await generate_three_musts(session, user.id, today)
    festnagel_line = await generate_festnagel(session, user.id, today)
    outlook = await generate_dropout_outlook(session, user.id, today)

    day_map = {
        "Monday": "Montag", "Tuesday": "Dienstag", "Wednesday": "Mittwoch",
        "Thursday": "Donnerstag", "Friday": "Freitag", "Saturday": "Samstag", "Sunday": "Sonntag",
    }
    day_name = day_map.get(today.strftime("%A"), today.strftime("%A"))
    date_str = today.strftime("%d.%m.%Y")

    brief_lines: list[str] = [f"{day_name}, {date_str}", ""]

    # ── STATUS ─────────────────────────────────────────────────────────────────
    brief_lines.append("━━ STATUS ━━")
    if status.get("energy") is not None:
        brief_lines.append(f"Energie: {status['energy']}/10")
    brief_lines.append(
        f"Aktive Objectives: {status['active_objectives']} | "
        f"KRs gefährdet: {status['krs_at_risk']}"
    )
    brief_lines.append("")

    # ── 3 MUSS ─────────────────────────────────────────────────────────────────
    if musts:
        brief_lines.append("━━ HEUTE — 3 MUSS ━━")
        for i, m in enumerate(musts, start=1):
            slot = f" — Slot: {m['slot']}" if m.get("slot") else ""
            prefix = {"task": "Task", "routine": "Routine", "kr": "KR"}.get(m["kind"], "")
            brief_lines.append(f"{i}. [{prefix}] {m['title']}{slot}")
        brief_lines.append("")

    # ── FESTNAGEL ──────────────────────────────────────────────────────────────
    brief_lines.append("━━ FESTNAGEL ━━")
    brief_lines.append(festnagel_line)
    brief_lines.append("")

    # ── KALENDER ───────────────────────────────────────────────────────────────
    if events:
        brief_lines.append("━━ KALENDER ━━")
        for e in events:
            time_str = e.start_time.strftime("%H:%M") if not e.all_day else "ganztägig"
            brief_lines.append(f"  {time_str} {e.title}")
        brief_lines.append("")

    # ── AUSBLICK (wahrscheinlich liegen bleibend) ──────────────────────────────
    if outlook:
        brief_lines.append("━━ AUSBLICK ━━")
        for line in outlook:
            brief_lines.append(f"  ⚠ {line}")
        brief_lines.append("")

    # ── Monday-only: Lebensbereich-Fokus (V3 P10) ─────────────────────────────
    if today.weekday() == 0:
        try:
            from bot.core.life_areas import get_weekly_focus_lines
            focus_lines = await get_weekly_focus_lines(session, user.id, today)
            if focus_lines:
                brief_lines.append("━━ DIESE WOCHE — LEBENSBEREICH-FOKUS ━━")
                brief_lines.extend(focus_lines)
                brief_lines.append("")
        except Exception:
            logger.exception("Monday life-area focus block failed (non-fatal)")

    # Overdue tasks — keep this as a hard signal even outside the new template
    if overdue:
        brief_lines.append(f"⚠ {len(overdue)} überfällige Tasks:")
        for t in overdue[:3]:
            brief_lines.append(f"  · {t.title} (fällig {t.due_date})")
        brief_lines.append("")

    brief_text = "\n".join(brief_lines).rstrip()

    # Append daily AI suggestions if available
    suggestions = await get_or_generate_suggestions(session, user, today)
    if suggestions:
        ai_lines = ["\n\n💡 Dein AI-Coach:"]
        fokus = suggestions.get("fokus_heute", [])
        if fokus:
            fokus_items = " · ".join(
                f.get("task", "") for f in fokus if f.get("task") and f["task"] != "—"
            )
            if fokus_items:
                ai_lines.append(f"→ Fokus heute: {fokus_items}")
        tipp = suggestions.get("tipp", "")
        if tipp:
            ai_lines.append(f"→ {tipp}")
        streak_warn = suggestions.get("streak_warnung")
        if streak_warn:
            ai_lines.append(f"⚠️ Streak-Alarm: {streak_warn}")
        brief_text += "\n".join(ai_lines)

    if supplement_view:
        def _line(items: list[dict], label: str) -> str:
            if not items:
                return f"- {label}: (Cycle-Pause)"
            names = ", ".join(x.get("name", "") for x in items[:5] if x.get("name"))
            suffix = " …" if len(items) > 5 else ""
            return f"- {label}: {names}{suffix}"

        morning_items = supplement_view["slot_checklist"]["morning"]
        midday_items = supplement_view["slot_checklist"]["midday"]
        evening_items = supplement_view["slot_checklist"]["evening"]
        hydration = supplement_view.get("hydration", {})
        water_range = f"{hydration.get('water_l_min', '?')}-{hydration.get('water_l_max', '?')}L"

        supplement_lines = [
            "\n\n🧪 Supplement-Plan heute",
            _line(morning_items, "Morgen"),
            _line(midday_items, "Mittag"),
            _line(evening_items, "Abend"),
            f"- Hydration: {water_range} Wasser + Elektrolyte tracken",
            f"⚕️ {supplement_view['medical_disclaimer']}",
        ]
        brief_text += "\n".join(supplement_lines)

    if fitness_view:
        split_name = fitness_view.get("split_name", "Training")
        focus = fitness_view.get("focus", "")
        ex_preview = ", ".join(fitness_view.get("exercises", [])[:4])
        if len(fitness_view.get("exercises", [])) > 4:
            ex_preview += " …"
        fitness_lines = [
            "\n\n🏋️ Fitness-Plan heute",
            f"- Split: {split_name}" + (f" ({focus})" if focus else ""),
        ]
        if ex_preview:
            fitness_lines.append(f"- Fokus-Übungen: {ex_preview}")
        brief_text += "\n".join(fitness_lines)

    # ─── Automation rule evaluation: sleep_low ────────────────────────────────
    try:
        from bot.core.rule_engine import evaluate_rules
        from bot.database.models import Log as _Log
        from sqlalchemy import and_ as _and_
        from datetime import datetime as _dt, timedelta as _td
        _yesterday = today - _td(days=1)
        _y_start = _dt.combine(_yesterday, _dt.min.time())
        _y_end = _dt.combine(_yesterday, _dt.max.time())
        _sleep_log = (await session.execute(
            select(_Log).where(_and_(
                _Log.user_id == user.id,
                _Log.log_type == "sleep",
                _Log.logged_at >= _y_start,
                _Log.logged_at <= _y_end,
            )).order_by(_Log.logged_at.desc()).limit(1)
        )).scalar_one_or_none()
        if _sleep_log:
            _sleep_hours = float(_sleep_log.data.get("hours", 99))
            if _sleep_hours < 7:
                rule_msgs = await evaluate_rules(
                    session, user,
                    "sleep_low",
                    {"sleep_hours": _sleep_hours, "value": _sleep_hours},
                )
                if rule_msgs:
                    brief_text += "\n\n⚡ Automatisierung:\n" + "\n".join(f"• {m}" for m in rule_msgs)
    except Exception:
        logger.exception("Automation rule evaluation failed in morning brief")

    # Priorities snapshot stored in DailyBrief for evening drift detection
    priorities_snapshot = [
        {"id": t.id, "title": t.title, "priority": t.priority}
        for t in tasks[:5]
    ]
    if supplement_view:
        priorities_snapshot.append(
            {
                "id": "supplement-stack",
                "title": "Supplement-Stack (Morgen/Mittag/Abend)",
                "priority": 2,
                "type": "protocol",
            }
        )
    if fitness_view and not fitness_view.get("is_rest_day"):
        priorities_snapshot.append(
            {
                "id": "fitness-split",
                "title": f"Workout: {fitness_view.get('split_name', 'Training')}",
                "priority": 2,
                "type": "protocol",
            }
        )
    return brief_text, priorities_snapshot


def _fallback_brief(
    tasks: list,
    routines: list,
    events: list,
    blocked_tasks: list,
    stale_objectives: list,
    suggested_blocks: list,
    name: str,
) -> str:
    lines = [f"☀️ Guten Morgen, {name}!\n"]
    if tasks:
        lines.append("🎯 TOP PRIORITÄTEN")
        for t in tasks[:3]:
            lines.append(f"  {t.priority}. {t.title}")
        lines.append("")
    if suggested_blocks:
        lines.append("⏱ FREIE SLOTS")
        for b in suggested_blocks:
            start = b.get("start_time", "—")
            end = b.get("end_time", "—")
            title = b.get("task_title") or "?"
            if start != "—":
                lines.append(f"  {start}–{end}: {title}")
        lines.append("")
    if blocked_tasks:
        lines.append("🔒 BLOCKIERT")
        for t in blocked_tasks[:3]:
            lines.append(f"  {t.title}")
        lines.append("")
    if stale_objectives:
        lines.append("📊 STAGNIERT")
        for obj in stale_objectives[:2]:
            lines.append(f"  {obj.title}")
        lines.append("")
    if routines:
        lines.append("📋 ROUTINEN HEUTE")
        for r in routines:
            lines.append(f"  ☐ {r.title}")
        lines.append("")
    if events:
        lines.append("📅 KALENDER")
        for e in events:
            time_str = e.start_time.strftime("%H:%M") if not e.all_day else "ganztägig"
            lines.append(f"  {time_str}: {e.title}")
        lines.append("")
    lines.append("Los geht's! 💪")
    return "\n".join(lines)


async def _get_or_create_daily_brief(
    session: AsyncSession, user_id: int, brief_date: date
) -> DailyBrief:
    result = await session.execute(
        select(DailyBrief).where(and_(
            DailyBrief.user_id == user_id,
            DailyBrief.brief_date == brief_date,
        ))
    )
    brief = result.scalar_one_or_none()
    if not brief:
        brief = DailyBrief(user_id=user_id, brief_date=brief_date)
        session.add(brief)
        await session.flush()
    return brief
