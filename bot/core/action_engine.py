"""Autonomous Action Engine — bridges insight detection → concrete actions.

Runs rule-based decisions (no GPT, $0/run) to create tasks, notifications,
and plan adjustments based on health data, KR progress, mood trends,
routine patterns, budget alerts, and more.

Entry points:
    run_morning_actions(session, user_id)   — 06:15 daily
    run_evening_actions(session, user_id)   — 21:30 daily
    run_weekly_actions(session, user_id)    — Sunday 09:00
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import (
    ActionQueueItem,
    AutopilotNotification,
    Budget,
    DailyContext,
    EveningCheckin,
    FinancialTransaction,
    KeyResult,
    Log,
    Objective,
    Routine,
    RoutineCompletion,
    Task,
    User,
    UserInsight,
)

logger = logging.getLogger(__name__)

# Guard: max auto-generated catch-up tasks per user per week
MAX_CATCHUP_TASKS_PER_WEEK = 3
CATCHUP_TAG = "[auto:catchup]"
SELFCARE_TAG = "[auto:selfcare]"
ACTION_SOURCE = "action_engine"


@dataclass
class ActionReport:
    """Summary of actions taken by the engine."""
    rules_fired: list[str] = field(default_factory=list)
    tasks_created: int = 0
    notifications_created: int = 0
    flags_set: list[str] = field(default_factory=list)


# ─── Morning Actions (06:15) ────────────────────────────────────────────────


async def run_morning_actions(session: AsyncSession, user_id: int) -> ActionReport:
    """Execute morning rules: health adjustment, KR lag, stale objectives."""
    report = ActionReport()

    try:
        await _rule_health_plan_adjustment(session, user_id, report)
    except Exception:
        logger.exception("Rule 1 (health adjustment) failed for user %d", user_id)

    try:
        await _rule_kr_lag_catchup(session, user_id, report)
    except Exception:
        logger.exception("Rule 2 (KR lag) failed for user %d", user_id)

    try:
        await _rule_stale_objective_escalation(session, user_id, report)
    except Exception:
        logger.exception("Rule 3 (stale objectives) failed for user %d", user_id)

    await session.flush()
    if report.rules_fired:
        logger.info(
            "Morning actions user %d: %d rules, %d tasks, %d notifs",
            user_id, len(report.rules_fired), report.tasks_created, report.notifications_created,
        )
    return report


# ─── Evening Actions (21:30) ────────────────────────────────────────────────


async def run_evening_actions(session: AsyncSession, user_id: int) -> ActionReport:
    """Execute evening rules: gap adjustment, mood alert, routine skip."""
    report = ActionReport()

    try:
        await _rule_gap_tomorrow_adjustment(session, user_id, report)
    except Exception:
        logger.exception("Rule 4 (gap adjustment) failed for user %d", user_id)

    try:
        await _rule_mood_trend_alert(session, user_id, report)
    except Exception:
        logger.exception("Rule 5 (mood alert) failed for user %d", user_id)

    try:
        await _rule_routine_skip_adjustment(session, user_id, report)
    except Exception:
        logger.exception("Rule 6 (routine skip) failed for user %d", user_id)

    await session.flush()
    if report.rules_fired:
        logger.info(
            "Evening actions user %d: %d rules, %d tasks, %d notifs",
            user_id, len(report.rules_fired), report.tasks_created, report.notifications_created,
        )
    return report


# ─── Weekly Actions (Sunday 09:00) ──────────────────────────────────────────


async def run_weekly_actions(session: AsyncSession, user_id: int) -> ActionReport:
    """Execute weekly rules: correlations, budget, achievements, momentum."""
    report = ActionReport()

    try:
        await _rule_correlation_coaching(session, user_id, report)
    except Exception:
        logger.exception("Rule 7 (correlation coaching) failed for user %d", user_id)

    try:
        await _rule_budget_alert(session, user_id, report)
    except Exception:
        logger.exception("Rule 8 (budget alert) failed for user %d", user_id)

    try:
        await _rule_achievement_nudge(session, user_id, report)
    except Exception:
        logger.exception("Rule 9 (achievement nudge) failed for user %d", user_id)

    try:
        await _rule_weekly_momentum(session, user_id, report)
    except Exception:
        logger.exception("Rule 10 (momentum) failed for user %d", user_id)

    await session.flush()
    if report.rules_fired:
        logger.info(
            "Weekly actions user %d: %d rules, %d tasks, %d notifs",
            user_id, len(report.rules_fired), report.tasks_created, report.notifications_created,
        )
    return report


# ─── Rule 1: Health-Based Plan Adjustment ────────────────────────────────────


async def _rule_health_plan_adjustment(
    session: AsyncSession, user_id: int, report: ActionReport
) -> None:
    """If sleep <6h or energy <=3 → flag low-energy day, notify."""
    today = date.today()
    yesterday = today - timedelta(days=1)
    y_start = datetime.combine(yesterday, datetime.min.time())
    y_end = datetime.combine(yesterday, datetime.max.time())

    # Check yesterday's sleep
    sleep_log = (await session.execute(
        select(Log).where(and_(
            Log.user_id == user_id,
            Log.log_type == "sleep",
            Log.logged_at >= y_start,
            Log.logged_at <= y_end,
        ))
    )).scalar_one_or_none()

    sleep_hours = float((sleep_log.data or {}).get("hours", 99)) if sleep_log else 99

    # Check today's energy (from morning context)
    ctx = (await session.execute(
        select(DailyContext).where(and_(
            DailyContext.user_id == user_id,
            DailyContext.date == today,
        ))
    )).scalar_one_or_none()

    energy = ctx.energy if ctx else None
    low_energy = sleep_hours < 6.0 or (energy is not None and energy <= 3)

    if not low_energy:
        return

    # Set flag in DailyContext
    if ctx:
        plan = dict(ctx.daily_plan or {})
        plan["low_energy_day"] = True
        plan["low_energy_reason"] = (
            f"Schlaf: {sleep_hours:.1f}h" if sleep_hours < 6.0
            else f"Energie: {energy}/10"
        )
        ctx.daily_plan = plan
    else:
        # Create minimal DailyContext with flag
        ctx = DailyContext(
            user_id=user_id,
            date=today,
            daily_plan={"low_energy_day": True, "low_energy_reason": f"Schlaf: {sleep_hours:.1f}h"},
        )
        session.add(ctx)

    # Create notification
    reason = f"Schlaf: {sleep_hours:.1f}h" if sleep_hours < 6 else f"Energie: {energy}/10"
    await _create_notification(
        session, user_id,
        notification_type="plan_reminder",
        title="⚡ Niedriger Energietag erkannt",
        body=f"{reason} — leichterer Plan empfohlen. Einfache Tasks priorisiert.",
    )

    report.rules_fired.append("health_plan_adjustment")
    report.notifications_created += 1
    report.flags_set.append("low_energy_day")


# ─── Rule 2: KR Lag → Catch-Up Tasks ────────────────────────────────────────


async def _rule_kr_lag_catchup(
    session: AsyncSession, user_id: int, report: ActionReport
) -> None:
    """If KR is >30% behind expected pace → create catch-up task."""
    today = date.today()

    # Count auto-generated tasks this week
    week_start = today - timedelta(days=today.weekday())
    existing_auto = (await session.execute(
        select(func.count()).select_from(Task).where(and_(
            Task.user_id == user_id,
            Task.title.contains(CATCHUP_TAG),
            Task.created_at >= datetime.combine(week_start, datetime.min.time()),
        ))
    )).scalar() or 0

    if existing_auto >= MAX_CATCHUP_TASKS_PER_WEEK:
        return

    # Find lagging KRs
    krs = (await session.execute(
        select(KeyResult).where(and_(
            KeyResult.user_id == user_id,
            KeyResult.status == "active",
        ))
    )).scalars().all()

    remaining_budget = MAX_CATCHUP_TASKS_PER_WEEK - existing_auto

    for kr in krs:
        if remaining_budget <= 0:
            break
        if not kr.target_value or kr.target_value <= 0:
            continue

        # Calculate expected progress based on time elapsed
        obj = (await session.execute(
            select(Objective).where(Objective.id == kr.objective_id)
        )).scalar_one_or_none() if kr.objective_id else None

        target_date = obj.target_date if obj and obj.target_date else None
        if not target_date or target_date <= today:
            continue

        created = kr.created_at.date() if kr.created_at else today - timedelta(days=30)
        total_days = max((target_date - created).days, 1)
        elapsed_days = max((today - created).days, 1)
        time_pct = elapsed_days / total_days

        progress_pct = (kr.current_value or 0) / kr.target_value
        gap = time_pct - progress_pct

        if gap < 0.30:  # Less than 30% behind
            continue

        # Check no existing catchup task for this KR
        existing = (await session.execute(
            select(func.count()).select_from(Task).where(and_(
                Task.key_result_id == kr.id,
                Task.status == "todo",
                Task.title.contains(CATCHUP_TAG),
            ))
        )).scalar() or 0

        if existing > 0:
            continue

        # Create catch-up task
        from bot.core.tasks import create_task
        task = await create_task(
            session, user_id,
            title=f"Sprint: {kr.title} {CATCHUP_TAG}",
            description=f"KR ist {int(gap * 100)}% hinter Plan. Fortschritt: {kr.current_value:.0f}/{kr.target_value:.0f}",
            priority=2,
            due_date=(today + timedelta(days=3)).isoformat(),
            key_result_id=kr.id,
            objective_id=kr.objective_id,
        )

        # Track in ActionQueue
        session.add(ActionQueueItem(
            user_id=user_id,
            state="suggested",
            item_type="task",
            title=task.title,
            reason=f"KR '{kr.title}' ist {int(gap*100)}% hinter dem Zeitplan",
            linked_task_id=task.id,
        ))

        report.tasks_created += 1
        remaining_budget -= 1

    if report.tasks_created > 0:
        report.rules_fired.append(f"kr_lag_catchup:{report.tasks_created}")


# ─── Rule 3: Stale Objective Escalation ──────────────────────────────────────


async def _rule_stale_objective_escalation(
    session: AsyncSession, user_id: int, report: ActionReport
) -> None:
    """If objective has blocker insight + zero open tasks → create kickstart task."""
    # Find blocker insights about inactive objectives
    insights = (await session.execute(
        select(UserInsight).where(and_(
            UserInsight.user_id == user_id,
            UserInsight.insight_type == "blocker",
            UserInsight.active == True,  # noqa: E712
            UserInsight.source == "auto_detected",
        ))
    )).scalars().all()

    for insight in insights:
        data = insight.data_basis or {}
        obj_id = data.get("objective_id")
        if not obj_id:
            continue

        # Check if objective has any open tasks
        open_count = (await session.execute(
            select(func.count()).select_from(Task).where(and_(
                Task.objective_id == obj_id,
                Task.status.in_(["todo", "in_progress"]),
            ))
        )).scalar() or 0

        if open_count > 0:
            continue

        # Check no existing kickstart task
        existing = (await session.execute(
            select(func.count()).select_from(Task).where(and_(
                Task.objective_id == obj_id,
                Task.status == "todo",
                Task.title.contains("Nächsten Schritt definieren"),
            ))
        )).scalar() or 0

        if existing > 0:
            continue

        obj = (await session.execute(
            select(Objective).where(Objective.id == obj_id)
        )).scalar_one_or_none()

        if not obj or obj.status != "active":
            continue

        from bot.core.tasks import create_task
        task = await create_task(
            session, user_id,
            title=f"Nächsten Schritt definieren für: {obj.title}",
            priority=1,
            due_date=(date.today() + timedelta(days=1)).isoformat(),
            objective_id=obj_id,
        )

        session.add(ActionQueueItem(
            user_id=user_id, state="suggested", item_type="task",
            title=task.title,
            reason=f"Ziel '{obj.title}' hat seit {data.get('days_inactive', 14)}+ Tagen keine Aktivität",
            linked_task_id=task.id,
        ))

        report.rules_fired.append(f"stale_objective:{obj_id}")
        report.tasks_created += 1


# ─── Rule 4: Gap → Tomorrow Adjustment ──────────────────────────────────────


async def _rule_gap_tomorrow_adjustment(
    session: AsyncSession, user_id: int, report: ActionReport
) -> None:
    """If <50% tasks completed today → reduce tomorrow's load."""
    today = date.today()

    checkin = (await session.execute(
        select(EveningCheckin).where(and_(
            EveningCheckin.user_id == user_id,
            EveningCheckin.date == today,
        ))
    )).scalar_one_or_none()

    if not checkin or not checkin.tasks_planned or checkin.tasks_planned == 0:
        return

    completion_rate = checkin.tasks_completed / checkin.tasks_planned

    if completion_rate >= 0.5:
        return

    # Set reduce_load flag for tomorrow
    tomorrow = today + timedelta(days=1)
    tomorrow_ctx = (await session.execute(
        select(DailyContext).where(and_(
            DailyContext.user_id == user_id,
            DailyContext.date == tomorrow,
        ))
    )).scalar_one_or_none()

    if tomorrow_ctx:
        plan = dict(tomorrow_ctx.daily_plan or {})
        plan["reduce_load"] = True
        tomorrow_ctx.daily_plan = plan
    else:
        session.add(DailyContext(
            user_id=user_id,
            date=tomorrow,
            daily_plan={"reduce_load": True},
        ))

    await _create_notification(
        session, user_id,
        notification_type="plan_reminder",
        title="📉 Tageslast angepasst",
        body=f"Heute {checkin.tasks_completed}/{checkin.tasks_planned} Tasks geschafft. "
             "Morgen weniger eingeplant für bessere Durchführung.",
    )

    report.rules_fired.append("gap_tomorrow_adjustment")
    report.notifications_created += 1
    report.flags_set.append("reduce_load")


# ─── Rule 5: Mood Trend Alert ───────────────────────────────────────────────


async def _rule_mood_trend_alert(
    session: AsyncSession, user_id: int, report: ActionReport
) -> None:
    """If 3-day mood avg drops >1.5 below 7-day avg → self-care task."""
    today = date.today()
    since_7d = datetime.combine(today - timedelta(days=7), datetime.min.time())
    since_3d = datetime.combine(today - timedelta(days=3), datetime.min.time())

    moods = (await session.execute(
        select(Log).where(and_(
            Log.user_id == user_id,
            Log.log_type == "mood",
            Log.logged_at >= since_7d,
        ))
    )).scalars().all()

    if len(moods) < 4:
        return

    all_scores = [float((m.data or {}).get("score", 0)) for m in moods if (m.data or {}).get("score")]
    recent_scores = [
        float((m.data or {}).get("score", 0))
        for m in moods
        if m.logged_at >= since_3d and (m.data or {}).get("score")
    ]

    if len(all_scores) < 4 or len(recent_scores) < 2:
        return

    avg_7d = sum(all_scores) / len(all_scores)
    avg_3d = sum(recent_scores) / len(recent_scores)
    drop = avg_7d - avg_3d

    if drop < 1.5:
        return

    # Check no existing self-care task
    existing = (await session.execute(
        select(func.count()).select_from(Task).where(and_(
            Task.user_id == user_id,
            Task.status == "todo",
            Task.title.contains(SELFCARE_TAG),
        ))
    )).scalar() or 0

    if existing > 0:
        return

    from bot.core.tasks import create_task
    task = await create_task(
        session, user_id,
        title=f"Selbstfürsorge: 30min für dich {SELFCARE_TAG}",
        description=f"Dein Mood ist in 3 Tagen von {avg_7d:.1f} auf {avg_3d:.1f} gefallen. Gönne dir eine Pause.",
        priority=2,
        due_date=today.isoformat(),
        category="general",
    )

    await _create_notification(
        session, user_id,
        notification_type="streak_warning",
        title="💛 Mood-Trend erkannt",
        body=f"Dein Mood ist von {avg_7d:.1f} auf {avg_3d:.1f} gefallen (3-Tage vs 7-Tage). Nimm dir Zeit für dich.",
    )

    report.rules_fired.append("mood_trend_alert")
    report.tasks_created += 1
    report.notifications_created += 1


# ─── Rule 6: Routine Skip → Adjustment ──────────────────────────────────────


async def _rule_routine_skip_adjustment(
    session: AsyncSession, user_id: int, report: ActionReport
) -> None:
    """If routine missed 3+ of last 5 days → suggest time adjustment."""
    today = date.today()
    since = datetime.combine(today - timedelta(days=5), datetime.min.time())

    routines = (await session.execute(
        select(Routine).where(and_(
            Routine.user_id == user_id,
            Routine.status == "active",
            Routine.frequency_human == "täglich",
        ))
    )).scalars().all()

    for routine in routines:
        completions = (await session.execute(
            select(func.count()).select_from(RoutineCompletion).where(and_(
                RoutineCompletion.routine_id == routine.id,
                RoutineCompletion.completed_at >= since,
            ))
        )).scalar() or 0

        if completions >= 3:  # 3+ of 5 days = ok
            continue

        # Check not already notified this week
        week_start = today - timedelta(days=today.weekday())
        already = (await session.execute(
            select(func.count()).select_from(AutopilotNotification).where(and_(
                AutopilotNotification.user_id == user_id,
                AutopilotNotification.title.contains(routine.title[:30]),
                AutopilotNotification.created_at >= datetime.combine(week_start, datetime.min.time()),
            ))
        )).scalar() or 0

        if already > 0:
            continue

        await _create_notification(
            session, user_id,
            notification_type="task_nudge",
            title=f"🔄 Routine anpassen: {routine.title}",
            body=f"Nur {completions}/5 Tage abgeschlossen. "
                 f"Aktuell: {routine.time_of_day}. Zeit anpassen oder vereinfachen?",
        )

        report.rules_fired.append(f"routine_skip:{routine.id}")
        report.notifications_created += 1


# ─── Rule 7: Correlation-Based Coaching ──────────────────────────────────────


async def _rule_correlation_coaching(
    session: AsyncSession, user_id: int, report: ActionReport
) -> None:
    """Turn strong correlations into weekly coaching tasks."""
    insights = (await session.execute(
        select(UserInsight).where(and_(
            UserInsight.user_id == user_id,
            UserInsight.insight_type == "correlation",
            UserInsight.active == True,  # noqa: E712
        ))
    )).scalars().all()

    today = date.today()
    from bot.core.tasks import create_task

    for insight in insights:
        data = insight.data_basis or {}
        r = abs(data.get("correlation_r", 0))
        if r < 0.5:
            continue

        # Map correlation to actionable task
        title_lower = insight.title.lower()
        task_title = None
        task_desc = insight.description

        if "schlaf" in title_lower and "mood" in title_lower:
            task_title = "Schlafziel: diese Woche jeden Tag vor 23:00 ins Bett"
        elif "training" in title_lower and ("mood" in title_lower or "energie" in title_lower):
            task_title = "3x Training diese Woche einplanen"
        elif "wasser" in title_lower and "energie" in title_lower:
            task_title = "Wasser-Tracking: diese Woche täglich >2L"
        elif "routine" in title_lower and "mood" in title_lower:
            task_title = "Routinen-Woche: alle täglichen Routinen durchziehen"

        if not task_title:
            continue

        # Don't duplicate
        existing = (await session.execute(
            select(func.count()).select_from(Task).where(and_(
                Task.user_id == user_id,
                Task.title == task_title,
                Task.status == "todo",
            ))
        )).scalar() or 0

        if existing > 0:
            continue

        task = await create_task(
            session, user_id,
            title=task_title,
            description=f"Basierend auf Korrelation: {task_desc}",
            priority=3,
            due_date=(today + timedelta(days=7)).isoformat(),
        )

        report.rules_fired.append(f"correlation_coaching:{insight.id}")
        report.tasks_created += 1


# ─── Rule 8: Budget Alert → Action ──────────────────────────────────────────


async def _rule_budget_alert(
    session: AsyncSession, user_id: int, report: ActionReport
) -> None:
    """If budget >80% used with >7 days left → create review task."""
    today = date.today()
    month_start = today.replace(day=1)
    days_left = ((month_start + timedelta(days=32)).replace(day=1) - today).days

    if days_left <= 7:
        return  # Too late in month, not actionable

    budgets = (await session.execute(
        select(Budget).where(Budget.user_id == user_id)
    )).scalars().all()

    from bot.core.tasks import create_task

    for budget in budgets:
        spent = (await session.execute(
            select(func.coalesce(func.sum(FinancialTransaction.amount), 0)).where(and_(
                FinancialTransaction.user_id == user_id,
                FinancialTransaction.type == "expense",
                FinancialTransaction.category == budget.category,
                FinancialTransaction.transaction_date >= month_start,
            ))
        )).scalar() or 0

        if budget.monthly_limit <= 0:
            continue

        usage_pct = spent / budget.monthly_limit
        if usage_pct < 0.80:
            continue

        remaining = budget.monthly_limit - spent
        task_title = f"Budget {budget.category}: noch €{remaining:.0f} übrig"

        existing = (await session.execute(
            select(func.count()).select_from(Task).where(and_(
                Task.user_id == user_id,
                Task.title.contains(f"Budget {budget.category}"),
                Task.status == "todo",
            ))
        )).scalar() or 0

        if existing > 0:
            continue

        await create_task(
            session, user_id,
            title=task_title,
            description=f"{int(usage_pct*100)}% verbraucht, {days_left} Tage übrig. Ausgaben prüfen.",
            priority=2,
            due_date=(today + timedelta(days=3)).isoformat(),
            category="finance",
        )

        report.rules_fired.append(f"budget_alert:{budget.category}")
        report.tasks_created += 1


# ─── Rule 9: Achievement Progress Nudge ──────────────────────────────────────


async def _rule_achievement_nudge(
    session: AsyncSession, user_id: int, report: ActionReport
) -> None:
    """Nudge user when close to unlocking an achievement."""
    from bot.database.models import Achievement, UserAchievement

    # Get already unlocked
    unlocked_ids = set((await session.execute(
        select(UserAchievement.achievement_id).where(UserAchievement.user_id == user_id)
    )).scalars().all())

    # Get all achievements
    all_achievements = (await session.execute(select(Achievement))).scalars().all()

    for ach in all_achievements:
        if ach.id in unlocked_ids:
            continue

        # Estimate progress based on condition_type
        progress = await _estimate_achievement_progress(session, user_id, ach)
        if progress is None or progress < 0.70:
            continue

        remaining = ach.condition_value - int(progress * ach.condition_value)
        if remaining <= 0:
            continue

        await _create_notification(
            session, user_id,
            notification_type="generic",
            title=f"🏆 Fast geschafft: {ach.emoji} {ach.title}",
            body=f"Noch {remaining} bis zum Unlock! (+{ach.xp_reward} XP)",
        )

        report.rules_fired.append(f"achievement_nudge:{ach.key}")
        report.notifications_created += 1


# ─── Rule 10: Weekly Momentum Score ─────────────────────────────────────────


async def _rule_weekly_momentum(
    session: AsyncSession, user_id: int, report: ActionReport
) -> None:
    """Compare this week's momentum to last week's. Alert on significant drop."""
    today = date.today()
    this_week_start = datetime.combine(today - timedelta(days=7), datetime.min.time())
    last_week_start = datetime.combine(today - timedelta(days=14), datetime.min.time())

    this_week = await _compute_momentum(session, user_id, this_week_start, this_week_start + timedelta(days=7))
    last_week = await _compute_momentum(session, user_id, last_week_start, last_week_start + timedelta(days=7))

    if last_week == 0:
        return

    drop = last_week - this_week
    if drop < 15:
        return

    await _create_notification(
        session, user_id,
        notification_type="streak_warning",
        title=f"📊 Momentum gesunken: {this_week}/100 (letzte Woche: {last_week})",
        body=f"Dein Momentum ist um {drop} Punkte gefallen. "
             "Fokussiere dich diese Woche auf deine Top-3 Prioritäten.",
    )

    report.rules_fired.append(f"weekly_momentum:{this_week}")
    report.notifications_created += 1


# ─── Helpers ─────────────────────────────────────────────────────────────────


async def _create_notification(
    session: AsyncSession,
    user_id: int,
    notification_type: str,
    title: str,
    body: str,
) -> AutopilotNotification:
    notif = AutopilotNotification(
        user_id=user_id,
        notification_type=notification_type,
        title=title,
        body=body,
        status="pending",
        source=ACTION_SOURCE,
    )
    session.add(notif)
    await session.flush()

    # Also send via Telegram + push
    try:
        from bot.telegram.sender import send_message
        await send_message(
            (await session.execute(
                select(User.telegram_id).where(User.id == user_id)
            )).scalar_one(),
            f"*{title}*\n{body}",
        )
    except Exception:
        logger.debug("Telegram send failed for notification %d", notif.id)

    try:
        from bot.core.push import send_push_if_subscribed
        await send_push_if_subscribed(
            session, user_id,
            title=title.replace("*", ""),
            body=body[:200],
            tag=notification_type,
        )
    except Exception:
        logger.debug("Push send failed for notification %d", notif.id)

    return notif


async def _compute_momentum(
    session: AsyncSession,
    user_id: int,
    start: datetime,
    end: datetime,
) -> int:
    """Simple momentum score 0-100: task completion + routine rate + logging."""
    # Tasks completed
    tasks_done = (await session.execute(
        select(func.count()).select_from(Task).where(and_(
            Task.user_id == user_id,
            Task.status == "done",
            Task.completed_at >= start,
            Task.completed_at < end,
        ))
    )).scalar() or 0

    tasks_total = max((await session.execute(
        select(func.count()).select_from(Task).where(and_(
            Task.user_id == user_id,
            Task.created_at >= start,
            Task.created_at < end,
        ))
    )).scalar() or 1, 1)

    task_rate = min(1.0, tasks_done / tasks_total)

    # Routine completions
    routine_comps = (await session.execute(
        select(func.count()).select_from(RoutineCompletion).where(and_(
            RoutineCompletion.user_id == user_id,
            RoutineCompletion.completed_at >= start,
            RoutineCompletion.completed_at < end,
        ))
    )).scalar() or 0

    active_routines = max((await session.execute(
        select(func.count()).select_from(Routine).where(and_(
            Routine.user_id == user_id,
            Routine.status == "active",
        ))
    )).scalar() or 1, 1)

    routine_rate = min(1.0, routine_comps / (active_routines * 7))

    # Logging activity
    log_days = (await session.execute(
        select(func.count(func.distinct(func.date(Log.logged_at)))).where(and_(
            Log.user_id == user_id,
            Log.logged_at >= start,
            Log.logged_at < end,
        ))
    )).scalar() or 0

    logging_rate = min(1.0, log_days / 7)

    return int((task_rate * 0.4 + routine_rate * 0.35 + logging_rate * 0.25) * 100)


async def _estimate_achievement_progress(
    session: AsyncSession, user_id: int, achievement
) -> Optional[float]:
    """Rough progress estimate for an achievement. Returns 0.0-1.0 or None."""
    ct = achievement.condition_type
    cv = achievement.condition_value
    if cv <= 0:
        return None

    if ct == "tasks_completed":
        count = (await session.execute(
            select(func.count()).select_from(Task).where(and_(
                Task.user_id == user_id, Task.status == "done",
            ))
        )).scalar() or 0
        return min(1.0, count / cv)

    elif ct == "objectives_completed":
        count = (await session.execute(
            select(func.count()).select_from(Objective).where(and_(
                Objective.user_id == user_id, Objective.status == "completed",
            ))
        )).scalar() or 0
        return min(1.0, count / cv)

    elif ct in ("workout_count", "workout_streak"):
        count = (await session.execute(
            select(func.count()).select_from(Log).where(and_(
                Log.user_id == user_id, Log.log_type == "workout",
            ))
        )).scalar() or 0
        return min(1.0, count / cv)

    elif ct == "reflection_count":
        from bot.database.models import WeeklyReflection
        count = (await session.execute(
            select(func.count()).select_from(WeeklyReflection).where(
                WeeklyReflection.user_id == user_id,
            )
        )).scalar() or 0
        return min(1.0, count / cv)

    return None
