"""CRUD operations for Objectives and Key Results."""
from datetime import date
from typing import Optional

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from bot.database.models import KeyResult, Log, Objective, Task


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
