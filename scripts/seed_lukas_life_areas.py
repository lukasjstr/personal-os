"""Seed Lukas's 9 life areas (V3 P10 — Mission Layer).

Idempotent upsert by (user_id, short_code). Also remaps existing Objectives
to their matching life area based on `category`, when --remap is passed.

Run on server:
    PYTHONPATH=. python3 scripts/seed_lukas_life_areas.py            # seed only
    PYTHONPATH=. python3 scripts/seed_lukas_life_areas.py --remap   # seed + remap
"""
from __future__ import annotations

import argparse
import asyncio

from sqlalchemy import select

from bot.database.connection import get_session
from bot.database.models import LifeArea, Objective, User


LUKAS_LIFE_AREAS: list[dict] = [
    {"name": "Mental/Emotional", "short_code": "mental",
     "vision": "emotional stability, loving, patient, caring, inspiring",
     "color_hex": "#9B7EBD", "priority": 5},
    {"name": "Physical", "short_code": "physical",
     "vision": "~85kg, Leonidas/Spartan look",
     "color_hex": "#D85A30", "priority": 3},
    {"name": "Character", "short_code": "character",
     "vision": "leader, multilingual, learn Greek & Latin, intellectually spar with dad",
     "color_hex": "#378ADD", "priority": 4},
    {"name": "Family", "short_code": "family",
     "vision": "loving family, wolf pack of winners sharing learnings",
     "color_hex": "#1D9E75", "priority": 4},
    {"name": "Romance", "short_code": "romance",
     "vision": "find wife material + live out sexual desires",
     "color_hex": "#D4537E", "priority": 5},
    {"name": "Money/Business", "short_code": "money",
     "vision": "10k/mo → 36M → own sports team, Shark Tank investor, Tuscan winery",
     "color_hex": "#EF9F27", "priority": 1},
    {"name": "Lifestyle", "short_code": "lifestyle",
     "vision": "location-independent, yacht, jet, UFC first row, Monaco GP",
     "color_hex": "#534AB7", "priority": 6},
    {"name": "Charity", "short_code": "charity",
     "vision": "buildings named after him, give back to fostering orgs",
     "color_hex": "#5DA37F", "priority": 7},
    {"name": "Spirituality", "short_code": "spirituality",
     "vision": "life is reality to experience, make the most of it",
     "color_hex": "#888780", "priority": 8},
]

# Map current Objective.category values to LifeArea short_codes
CATEGORY_TO_SHORT: dict[str, str] = {
    "health": "physical",
    "fitness": "physical",
    "business": "money",
    "finance": "money",
    "learning": "character",
    "personal_growth": "character",
    "personal": "mental",       # default fallback
    "relationships": "family",
    "spiritual": "spirituality",
}


async def seed_for_user(user_id: int) -> dict[str, int]:
    """Upsert the 9 areas. Returns {short_code: id}."""
    async with get_session() as session:
        existing = (await session.execute(
            select(LifeArea).where(LifeArea.user_id == user_id)
        )).scalars().all()
        by_code = {a.short_code: a for a in existing}

        out: dict[str, int] = {}
        for spec in LUKAS_LIFE_AREAS:
            code = spec["short_code"]
            row = by_code.get(code)
            if row is None:
                row = LifeArea(
                    user_id=user_id,
                    name=spec["name"],
                    short_code=code,
                    vision=spec["vision"],
                    priority=spec["priority"],
                    color_hex=spec["color_hex"],
                )
                session.add(row)
                await session.flush()
            else:
                # Update meta but keep current_state (user-edited)
                row.name = spec["name"]
                row.vision = spec["vision"]
                row.color_hex = spec["color_hex"]
                if row.priority == 5 and spec["priority"] != 5:
                    row.priority = spec["priority"]
            out[code] = row.id
        return out


async def remap_existing_objectives(user_id: int, code_to_id: dict[str, int]) -> int:
    """Map Objective.category → LifeArea.short_code → set Objective.life_area_id.
    Only updates rows where life_area_id IS NULL. Returns count of rows changed.
    """
    n = 0
    async with get_session() as session:
        objs = (await session.execute(
            select(Objective).where(Objective.user_id == user_id)
        )).scalars().all()
        for obj in objs:
            if obj.life_area_id is not None:
                continue
            short = CATEGORY_TO_SHORT.get((obj.category or "").lower())
            if not short:
                continue
            new_id = code_to_id.get(short)
            if new_id is None:
                continue
            obj.life_area_id = new_id
            n += 1
        await session.flush()
    return n


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed Lukas's 9 life areas (P10).")
    parser.add_argument("--user-id", type=int, default=None,
                        help="Target user id. Default: every user.")
    parser.add_argument("--remap", action="store_true",
                        help="Also map existing objectives by category → life_area_id.")
    args = parser.parse_args()

    async def run() -> None:
        if args.user_id is not None:
            targets = [args.user_id]
        else:
            async with get_session() as session:
                targets = list((await session.execute(select(User.id))).scalars().all())
        if not targets:
            print("No users found.")
            return
        for uid in targets:
            code_to_id = await seed_for_user(uid)
            print(f"user_id={uid}: seeded {len(code_to_id)} areas")
            if args.remap:
                n = await remap_existing_objectives(uid, code_to_id)
                print(f"user_id={uid}: remapped {n} objectives")

    asyncio.run(run())


if __name__ == "__main__":
    main()
