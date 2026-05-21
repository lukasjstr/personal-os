"""CRUD operations for Objectives and Key Results."""
from datetime import date, datetime
from typing import Optional

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from bot.config import settings
from bot.database.models import KeyResult, Log, Objective, Task
from bot.core.tasks import create_task as _create_task


# ─── V3 P08 — Expansion Guard ────────────────────────────────────────────────


class ExpansionGuardException(Exception):
    """Raised when the hard limit on active objectives is hit."""


PRIORITY1_THRESHOLD: int = 8  # priority_weight >= 8 is "Priority 1"


async def _resolve_life_area_id(
    session: AsyncSession, user_id: int, short_code: Optional[str]
) -> Optional[int]:
    """Look up LifeArea.id for (user_id, short_code). Returns None if absent."""
    if not short_code:
        return None
    from bot.database.models import LifeArea
    row = (await session.execute(
        select(LifeArea).where(and_(
            LifeArea.user_id == user_id,
            LifeArea.short_code == short_code.lower().strip(),
        ))
    )).scalar_one_or_none()
    return row.id if row else None


async def create_objective_with_guard(
    session: AsyncSession,
    user_id: int,
    title: str,
    category: str,
    description: Optional[str] = None,
    target_date: Optional[str] = None,
    priority_weight: int = 5,
    life_area_short_code: Optional[str] = None,
) -> dict:
    """Create an Objective, enforcing soft + hard expansion limits.

    Returns:
        {
          "objective": Objective,
          "warning": Optional[str],    # soft-limit-Warnung
          "stats": {"active_total": int, "priority1_count": int},
        }

    Raises:
        ExpansionGuardException — when total active >= hard limit.
    """
    active = (await session.execute(
        select(Objective).where(and_(
            Objective.user_id == user_id,
            Objective.status == "active",
        ))
    )).scalars().all()
    total_active = len(active)
    priority1_count = sum(
        1 for o in active if (o.priority_weight or 0) >= PRIORITY1_THRESHOLD
    )

    if total_active >= settings.expansion_hard_limit_total:
        raise ExpansionGuardException(
            f"HARD LIMIT: {settings.expansion_hard_limit_total} aktive Ziele "
            f"sind das Maximum. Eines muss erst pausieren (siehe /cut)."
        )

    warning: Optional[str] = None
    if (settings.expansion_warning_enabled
            and priority_weight >= PRIORITY1_THRESHOLD
            and priority1_count >= settings.expansion_soft_limit_priority1):
        warning = (
            f"SOFT LIMIT: Du hast bereits {priority1_count} Priority-1-Ziele. "
            f"Limit ist {settings.expansion_soft_limit_priority1}. "
            f"Welches degradierst du auf Priority 2?"
        )

    obj = await create_objective(
        session, user_id, title=title, category=category,
        description=description, target_date=target_date,
    )
    if priority_weight != 5:
        obj.priority_weight = priority_weight
    # V3 P10 — link to mission layer
    life_area_id = await _resolve_life_area_id(session, user_id, life_area_short_code)
    if life_area_id is not None:
        obj.life_area_id = life_area_id
    await session.flush()

    new_priority1 = priority1_count + (1 if priority_weight >= PRIORITY1_THRESHOLD else 0)
    return {
        "objective": obj,
        "warning": warning,
        "stats": {"active_total": total_active + 1, "priority1_count": new_priority1},
    }


async def suggest_objective_to_cut(
    session: AsyncSession, user_id: int
) -> Optional[dict]:
    """Identify the weakest active objective. Returns a dict with metrics or None."""
    objs = (await session.execute(
        select(Objective).where(and_(
            Objective.user_id == user_id,
            Objective.status == "active",
        ))
    )).scalars().all()
    if not objs:
        return None

    today = date.today()
    scored: list[tuple[int, dict]] = []
    for obj in objs:
        last_log = (await session.execute(
            select(func.max(Log.logged_at))
            .join(KeyResult, Log.key_result_id == KeyResult.id)
            .where(KeyResult.objective_id == obj.id)
        )).scalar()
        if last_log:
            days_stale = (today - last_log.date()).days
        else:
            ref = obj.updated_at or obj.created_at
            days_stale = (today - ref.date()).days if ref else 30

        # Completion rate: sum of (current/target) ratios across KRs
        krs = (await session.execute(
            select(KeyResult).where(KeyResult.objective_id == obj.id)
        )).scalars().all()
        ratios: list[float] = []
        for kr in krs:
            if kr.target_value and kr.target_value > 0:
                ratios.append(min(1.0, kr.current_value / kr.target_value))
        completion = sum(ratios) / max(1, len(ratios))

        priority_weight = obj.priority_weight or 5
        score = (days_stale * 2) - int(completion * 100) + (10 - priority_weight)
        scored.append((score, {
            "id": obj.id,
            "title": obj.title,
            "category": obj.category,
            "priority_weight": priority_weight,
            "days_stale": days_stale,
            "completion": round(completion, 2),
            "score": score,
        }))

    scored.sort(key=lambda x: -x[0])
    return scored[0][1] if scored else None


async def pause_objective_for_cut(
    session: AsyncSession, user_id: int, objective_id: int, reason: str = "expansion_cut"
) -> Optional[Objective]:
    """Pause an objective owned by the user. Returns the row or None."""
    obj = (await session.execute(
        select(Objective).where(and_(
            Objective.id == objective_id,
            Objective.user_id == user_id,
        ))
    )).scalar_one_or_none()
    if obj is None:
        return None
    obj.status = "paused"
    obj.paused_at = datetime.utcnow()
    obj.paused_reason = reason
    await session.flush()
    return obj


async def create_objective(
    session: AsyncSession,
    user_id: int,
    title: str,
    category: str,
    description: Optional[str] = None,
    target_date: Optional[str] = None,
) -> Objective:
    """Create a new Objective."""
    parsed_date = None
    if target_date:
        try:
            parsed_date = date.fromisoformat(target_date)
        except ValueError:
            pass

    obj = Objective(
        user_id=user_id,
        title=title,
        category=category,
        description=description,
        target_date=parsed_date,
        status="active",
    )
    session.add(obj)
    await session.flush()
    return obj


async def create_key_result(
    session: AsyncSession,
    user_id: int,
    objective_id: int,
    title: str,
    metric_type: str,
    target_value: Optional[float] = None,
    unit: Optional[str] = None,
    frequency: str = "weekly",
    target_date: Optional[str] = None,
) -> KeyResult:
    """Create a new Key Result under an Objective."""
    parsed_date = None
    if target_date:
        try:
            parsed_date = date.fromisoformat(target_date)
        except ValueError:
            pass

    kr = KeyResult(
        objective_id=objective_id,
        user_id=user_id,
        title=title,
        metric_type=metric_type,
        target_value=target_value,
        unit=unit,
        frequency=frequency,
        target_date=parsed_date,
        status="active",
    )
    session.add(kr)
    await session.flush()
    return kr


async def suggest_tasks_for_objective(
    session: AsyncSession,
    user_id: int,
    objective_id: int,
    tasks: list[dict],
) -> str:
    """Bulk-create suggested tasks for a given objective."""
    result = await session.execute(
        select(Objective).where(and_(Objective.id == objective_id, Objective.user_id == user_id))
    )
    obj = result.scalar_one_or_none()
    if not obj:
        return f"Objective #{objective_id} nicht gefunden."

    created_lines = []
    for t in tasks:
        task = await _create_task(
            session,
            user_id,
            title=t["title"],
            description=t.get("description"),
            priority=t.get("priority", 3),
            objective_id=objective_id,
        )
        created_lines.append(f"  ☐ #{task.id} {task.title} [P{task.priority}]")

    if not created_lines:
        return f"Keine Tasks für Objective #{objective_id} erstellt."

    return (
        f"✅ {len(created_lines)} Tasks für *{obj.title}* erstellt:\n"
        + "\n".join(created_lines)
        + "\n\nDiese Tasks sind jetzt mit dem Objective verknüpft."
    )


async def get_active_objectives(session: AsyncSession, user_id: int) -> str:
    """Return a formatted string of all active objectives with key results."""
    result = await session.execute(
        select(Objective)
        .options(selectinload(Objective.key_results))
        .where(and_(Objective.user_id == user_id, Objective.status == "active"))
        .order_by(Objective.created_at)
    )
    objectives = result.scalars().all()

    if not objectives:
        return "Keine aktiven Ziele gefunden."

    lines = ["Aktive Ziele:"]
    for obj in objectives:
        lines.append(f"\n🎯 #{obj.id} {obj.title} [{obj.category}]")
        for kr in obj.key_results:
            if kr.status == "active":
                progress = ""
                if kr.target_value and kr.target_value > 0:
                    pct = int((kr.current_value / kr.target_value) * 100)
                    progress = f" — {pct}% ({kr.current_value}/{kr.target_value} {kr.unit or ''})"
                lines.append(f"  📊 KR#{kr.id}: {kr.title}{progress}")
    return "\n".join(lines)


async def list_active_objectives(session: AsyncSession, user_id: int) -> dict:
    """Return active objectives with stale_days for expansion-protection (V3 P03).

    Returns:
        {
          "count": int,
          "objectives": [
            {"id": int, "title": str, "category": str, "stale_days": int|None}
          ]
        }
    stale_days = days since last Log on any KR belonging to this objective.
    None if no logs ever recorded.
    """
    result = await session.execute(
        select(Objective)
        .where(and_(Objective.user_id == user_id, Objective.status == "active"))
        .order_by(Objective.created_at)
    )
    objectives = result.scalars().all()
    today = date.today()
    out: list[dict] = []
    for obj in objectives:
        last_log_dt = (await session.execute(
            select(func.max(Log.logged_at))
            .join(KeyResult, Log.key_result_id == KeyResult.id)
            .where(KeyResult.objective_id == obj.id)
        )).scalar()
        stale_days: Optional[int] = None
        if isinstance(last_log_dt, datetime):
            stale_days = (today - last_log_dt.date()).days
        out.append({
            "id": obj.id,
            "title": obj.title,
            "category": obj.category,
            "stale_days": stale_days,
        })
    return {"count": len(out), "objectives": out}


async def get_progress_report(session: AsyncSession, user_id: int, objective_id: int) -> str:
    """Return a detailed progress report for an objective."""
    result = await session.execute(
        select(Objective)
        .options(selectinload(Objective.key_results))
        .where(and_(Objective.id == objective_id, Objective.user_id == user_id))
    )
    obj = result.scalar_one_or_none()
    if not obj:
        return f"Objective #{objective_id} nicht gefunden."

    lines = [f"📊 Fortschrittsbericht: {obj.title}"]
    lines.append(f"Status: {obj.status} | Kategorie: {obj.category}")
    if obj.target_date:
        lines.append(f"Zieldatum: {obj.target_date}")

    total_pct = []
    for kr in obj.key_results:
        pct = 0
        if kr.target_value and kr.target_value > 0:
            pct = min(100, int((kr.current_value / kr.target_value) * 100))
            total_pct.append(pct)
        bar = "█" * (pct // 10) + "░" * (10 - pct // 10)
        lines.append(f"\n  KR#{kr.id}: {kr.title}")
        lines.append(f"  [{bar}] {pct}% ({kr.current_value}/{kr.target_value or '?'} {kr.unit or ''})")

    if total_pct:
        avg = sum(total_pct) // len(total_pct)
        lines.append(f"\n  Gesamt: {avg}% abgeschlossen")

    return "\n".join(lines)
