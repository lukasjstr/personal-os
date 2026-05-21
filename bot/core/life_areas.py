"""V3 P10 — Mission Layer helpers.

LifeArea is the top of the strategy hierarchy:
    LifeArea (5+ yr vision) → Objective (quarter) → KR (week) → Task/Log
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import KeyResult, LifeArea, Log, Objective, Task


async def list_life_areas(session: AsyncSession, user_id: int) -> list[LifeArea]:
    """Return all life areas for a user, ordered by priority asc then id."""
    return list((await session.execute(
        select(LifeArea).where(LifeArea.user_id == user_id)
        .order_by(LifeArea.priority.asc(), LifeArea.id.asc())
    )).scalars().all())


async def get_area_stats(
    session: AsyncSession, user_id: int, area_id: int, today: Optional[date] = None
) -> dict:
    """Return per-area summary: active objectives, stale_days, last log."""
    if today is None:
        today = date.today()
    active_count = (await session.execute(
        select(func.count()).select_from(Objective).where(and_(
            Objective.user_id == user_id,
            Objective.life_area_id == area_id,
            Objective.status == "active",
        ))
    )).scalar() or 0

    last_log = (await session.execute(
        select(func.max(Log.logged_at))
        .join(KeyResult, Log.key_result_id == KeyResult.id)
        .join(Objective, KeyResult.objective_id == Objective.id)
        .where(and_(
            Objective.user_id == user_id,
            Objective.life_area_id == area_id,
        ))
    )).scalar()

    stale_days: Optional[int] = None
    if last_log is not None:
        stale_days = (today - last_log.date()).days

    return {
        "active_objectives": int(active_count),
        "last_log_at": last_log.isoformat() if last_log else None,
        "stale_days": stale_days,
    }


async def get_weekly_focus_lines(
    session: AsyncSession, user_id: int, today: date
) -> list[str]:
    """Build the Monday-brief 'Lebensbereich-Fokus' lines (max 3 areas).

    Selection: areas with at least 1 active objective, sorted by:
      (stale_days desc, priority asc, active_objectives desc).
    """
    areas = await list_life_areas(session, user_id)
    enriched: list[tuple[LifeArea, dict]] = []
    for area in areas:
        stats = await get_area_stats(session, user_id, area.id, today)
        if stats["active_objectives"] == 0:
            continue
        enriched.append((area, stats))

    enriched.sort(key=lambda pair: (
        -(pair[1]["stale_days"] or 0),
        pair[0].priority,
        -pair[1]["active_objectives"],
    ))

    out: list[str] = []
    for i, (area, stats) in enumerate(enriched[:3], start=1):
        vision_short = (area.vision or "").split(",")[0].strip() or area.name
        sample_obj = (await session.execute(
            select(Objective).where(and_(
                Objective.user_id == user_id,
                Objective.life_area_id == area.id,
                Objective.status == "active",
            )).order_by(Objective.priority_weight.desc()).limit(1)
        )).scalar_one_or_none()
        obj_str = f" → {sample_obj.title}" if sample_obj else ""
        stale = stats["stale_days"]
        stale_str = f" ({stale}d stale)" if stale is not None and stale > 7 else ""
        out.append(f"  {i}. {area.name}: {vision_short}{obj_str}{stale_str}")
    return out
