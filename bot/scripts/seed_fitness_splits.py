"""Seed fitness splits for user_id=1 from docs/protocols/lukas_fitness_split.json.

Usage:
    python -m bot.scripts.seed_fitness_splits
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from sqlalchemy import select

from bot.database.connection import get_session
from bot.database.models import FitnessSplit


PROTOCOL_PATH = Path(__file__).resolve().parents[2] / "docs" / "protocols" / "lukas_fitness_split.json"
USER_ID = 1


async def seed() -> None:
    protocol = json.loads(PROTOCOL_PATH.read_text())
    rotation: list[str] = protocol["meta"]["rotation"]
    splits_data: dict = protocol["splits"]

    async with get_session() as session:
        result = await session.execute(
            select(FitnessSplit).where(FitnessSplit.user_id == USER_ID)
        )
        existing = result.scalars().all()
        if existing:
            print(f"[seed_fitness_splits] Already have {len(existing)} splits for user_id={USER_ID} — skip.")
            return

        for order, name in enumerate(rotation, start=1):
            split_def = splits_data[name]
            exercises = [{"name": ex} for ex in split_def["exercises"]]
            split = FitnessSplit(
                user_id=USER_ID,
                name=name,
                exercises=exercises,
                order_in_rotation=order,
            )
            session.add(split)

        await session.commit()
        print(f"[seed_fitness_splits] Created {len(rotation)} splits for user_id={USER_ID}: {rotation}")


def main() -> None:
    asyncio.run(seed())


if __name__ == "__main__":
    main()
