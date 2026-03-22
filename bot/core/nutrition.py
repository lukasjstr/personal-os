"""Structured nutrition tracking — FoodEntry CRUD, daily summaries, and macro analytics."""
from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import FoodEntry

logger = logging.getLogger(__name__)


async def create_food_entry(
    session: AsyncSession,
    user_id: int,
    food_name: str,
    meal_type: str = "snack",
    quantity: Optional[float] = None,
    unit: Optional[str] = None,
    calories: Optional[float] = None,
    protein_g: Optional[float] = None,
    carbs_g: Optional[float] = None,
    fat_g: Optional[float] = None,
    fiber_g: Optional[float] = None,
    sodium_mg: Optional[float] = None,
    sugar_g: Optional[float] = None,
    notes: Optional[str] = None,
    source: str = "text",
    raw_input: Optional[str] = None,
    logged_date: Optional[date] = None,
) -> FoodEntry:
    """Create and persist a structured food entry."""
    entry = FoodEntry(
        user_id=user_id,
        logged_date=logged_date or date.today(),
        meal_type=meal_type,
        food_name=food_name,
        quantity=quantity,
        unit=unit,
        calories=calories,
        protein_g=protein_g,
        carbs_g=carbs_g,
        fat_g=fat_g,
        fiber_g=fiber_g,
        sodium_mg=sodium_mg,
        sugar_g=sugar_g,
        notes=notes,
        source=source,
        raw_input=raw_input,
    )
    session.add(entry)
    await session.flush()
    logger.info(
        "FoodEntry created: user=%d meal=%s food=%s cal=%s sodium=%s",
        user_id, meal_type, food_name, calories, sodium_mg,
    )
    return entry


async def get_daily_nutrition(
    session: AsyncSession,
    user_id: int,
    target_date: Optional[date] = None,
) -> dict:
    """Return aggregated macro totals and meal breakdown for a given day."""
    target_date = target_date or date.today()

    entries = (await session.execute(
        select(FoodEntry).where(and_(
            FoodEntry.user_id == user_id,
            FoodEntry.logged_date == target_date,
        )).order_by(FoodEntry.logged_at)
    )).scalars().all()

    if not entries:
        return {
            "date": target_date.isoformat(),
            "meals": [],
            "totals": _empty_totals(),
            "has_data": False,
        }

    meals_by_type: dict[str, list[dict]] = defaultdict(list)
    totals = _empty_totals()

    for e in entries:
        item = {
            "id": e.id,
            "food_name": e.food_name,
            "quantity": e.quantity,
            "unit": e.unit,
            "calories": e.calories,
            "protein_g": e.protein_g,
            "carbs_g": e.carbs_g,
            "fat_g": e.fat_g,
            "fiber_g": e.fiber_g,
            "sodium_mg": e.sodium_mg,
            "sugar_g": e.sugar_g,
        }
        meals_by_type[e.meal_type].append(item)
        for key in ["calories", "protein_g", "carbs_g", "fat_g", "fiber_g", "sodium_mg", "sugar_g"]:
            val = getattr(e, key)
            if val is not None:
                totals[key] = (totals[key] or 0) + val

    # Round totals
    totals = {k: round(v, 1) if v is not None else None for k, v in totals.items()}

    return {
        "date": target_date.isoformat(),
        "meals": dict(meals_by_type),
        "totals": totals,
        "has_data": True,
        "entry_count": len(entries),
    }


async def get_sodium_by_date(
    session: AsyncSession,
    user_id: int,
    since: datetime,
) -> dict[str, float]:
    """Return daily sodium totals (mg) indexed by date string."""
    entries = (await session.execute(
        select(FoodEntry).where(and_(
            FoodEntry.user_id == user_id,
            FoodEntry.logged_at >= since,
            FoodEntry.sodium_mg.isnot(None),
        ))
    )).scalars().all()
    daily: dict[str, float] = defaultdict(float)
    for e in entries:
        daily[e.logged_date.isoformat()] += e.sodium_mg or 0
    return dict(daily)


async def get_calories_by_date(
    session: AsyncSession,
    user_id: int,
    since: datetime,
) -> dict[str, float]:
    """Return daily calorie totals indexed by date string."""
    entries = (await session.execute(
        select(FoodEntry).where(and_(
            FoodEntry.user_id == user_id,
            FoodEntry.logged_at >= since,
            FoodEntry.calories.isnot(None),
        ))
    )).scalars().all()
    daily: dict[str, float] = defaultdict(float)
    for e in entries:
        daily[e.logged_date.isoformat()] += e.calories or 0
    return dict(daily)


async def get_protein_by_date(
    session: AsyncSession,
    user_id: int,
    since: datetime,
) -> dict[str, float]:
    """Return daily protein totals (g) indexed by date string."""
    entries = (await session.execute(
        select(FoodEntry).where(and_(
            FoodEntry.user_id == user_id,
            FoodEntry.logged_at >= since,
            FoodEntry.protein_g.isnot(None),
        ))
    )).scalars().all()
    daily: dict[str, float] = defaultdict(float)
    for e in entries:
        daily[e.logged_date.isoformat()] += e.protein_g or 0
    return dict(daily)


async def get_nutrition_history(
    session: AsyncSession,
    user_id: int,
    days: int = 90,
) -> list[dict]:
    """Return per-day nutrition summary for the last N days."""
    since = date.today() - timedelta(days=days)
    entries = (await session.execute(
        select(FoodEntry).where(and_(
            FoodEntry.user_id == user_id,
            FoodEntry.logged_date >= since,
        )).order_by(FoodEntry.logged_date.desc(), FoodEntry.logged_at.desc())
    )).scalars().all()

    by_date: dict[str, dict] = {}
    for e in entries:
        d = e.logged_date.isoformat()
        if d not in by_date:
            by_date[d] = {"date": d, **_empty_totals()}
        for key in ["calories", "protein_g", "carbs_g", "fat_g", "sodium_mg"]:
            val = getattr(e, key)
            if val is not None:
                by_date[d][key] = (by_date[d].get(key) or 0) + val

    return sorted(by_date.values(), key=lambda x: x["date"], reverse=True)


async def format_daily_nutrition_summary(
    session: AsyncSession,
    user_id: int,
    target_date: Optional[date] = None,
) -> str:
    """Format a human-readable nutrition summary for Telegram."""
    data = await get_daily_nutrition(session, user_id, target_date)
    if not data["has_data"]:
        return "Noch keine Mahlzeiten für heute geloggt."

    t = data["totals"]
    lines = [f"🍽️ *Ernährung {data['date']}*\n"]

    meal_order = ["breakfast", "lunch", "dinner", "snack"]
    meal_emoji = {"breakfast": "🌅", "lunch": "☀️", "dinner": "🌙", "snack": "🍎"}
    meal_label = {"breakfast": "Frühstück", "lunch": "Mittagessen", "dinner": "Abendessen", "snack": "Snack"}

    for meal_type in meal_order:
        items = data["meals"].get(meal_type, [])
        if not items:
            continue
        emoji = meal_emoji.get(meal_type, "🍴")
        label = meal_label.get(meal_type, meal_type)
        lines.append(f"{emoji} *{label}:*")
        for item in items:
            name = item["food_name"]
            cal = f" ({int(item['calories'])} kcal)" if item.get("calories") else ""
            lines.append(f"  • {name}{cal}")

    lines.append("")
    lines.append("📊 *Gesamt:*")
    if t.get("calories"):
        lines.append(f"  🔥 Kalorien: {int(t['calories'])} kcal")
    if t.get("protein_g"):
        lines.append(f"  💪 Protein: {int(t['protein_g'])}g")
    if t.get("carbs_g"):
        lines.append(f"  🌾 Kohlenhydrate: {int(t['carbs_g'])}g")
    if t.get("fat_g"):
        lines.append(f"  🫒 Fett: {int(t['fat_g'])}g")
    if t.get("sodium_mg"):
        sodium = int(t["sodium_mg"])
        sodium_emoji = "⚠️" if sodium > 2300 else "✅"
        lines.append(f"  {sodium_emoji} Natrium: {sodium}mg")

    return "\n".join(lines)


def _empty_totals() -> dict:
    return {
        "calories": None,
        "protein_g": None,
        "carbs_g": None,
        "fat_g": None,
        "fiber_g": None,
        "sodium_mg": None,
        "sugar_g": None,
    }
