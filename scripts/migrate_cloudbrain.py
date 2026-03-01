"""Migration script: Cloudbrain SQLite → Personal OS PostgreSQL.

Reads /data/db/cloudbrain.db and migrates:
- life_areas → objectives (category mapped)
- goals → objectives
- tasks → tasks
- entries → logs
"""
import asyncio
import json
import sys
import os
from datetime import datetime
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import aiosqlite
from sqlalchemy import select

from bot.database.connection import AsyncSessionLocal
from bot.database.models import Log, Objective, Task, User

CLOUDBRAIN_DB = os.environ.get("CLOUDBRAIN_DB", "/data/db/cloudbrain.db")


def row_to_dict(row, cursor_description) -> dict:
    """Convert aiosqlite Row to dict using cursor description."""
    return {col[0]: row[i] for i, col in enumerate(cursor_description)}

CATEGORY_MAP = {
    "health": "health",
    "fitness": "fitness",
    "business": "business",
    "finance": "finance",
    "personal": "personal",
    "work": "business",
    "family": "personal",
    "learning": "personal",
    "mind": "personal",
    "body": "fitness",
}


def map_category(raw: Optional[str]) -> str:
    if not raw:
        return "personal"
    return CATEGORY_MAP.get(raw.lower(), "personal")


async def migrate(telegram_id: int) -> None:
    if not os.path.exists(CLOUDBRAIN_DB):
        print(f"ERROR: Cloudbrain DB not found at {CLOUDBRAIN_DB}")
        sys.exit(1)

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        if not user:
            print(f"ERROR: User with telegram_id={telegram_id} not found in DB. Send a message to the bot first.")
            sys.exit(1)

        print(f"Migrating to user #{user.id} ({user.first_name})")

        async with aiosqlite.connect(CLOUDBRAIN_DB) as db:
            # life_areas → objectives
            area_id_map: dict[int, int] = {}
            try:
                async with db.execute("SELECT * FROM life_areas") as cursor:
                    desc = cursor.description
                    rows = await cursor.fetchall()
                areas = [row_to_dict(r, desc) for r in rows]
                print(f"  Migrating {len(areas)} life areas...")
                for area in areas:
                    obj = Objective(
                        user_id=user.id,
                        title=area.get("name_de") or area.get("name") or area.get("slug", "unknown"),
                        description=area.get("description"),
                        category=map_category(area.get("slug")),
                        status="active",
                    )
                    session.add(obj)
                    await session.flush()
                    area_id_map[area["id"]] = obj.id
                    print(f"    ✓ {obj.title}")
            except Exception as e:
                print(f"  life_areas error: {e}")

            # goals → objectives
            goal_id_map: dict[int, int] = {}
            try:
                async with db.execute("SELECT * FROM goals WHERE is_deleted = 0") as cursor:
                    desc = cursor.description
                    rows = await cursor.fetchall()
                goals = [row_to_dict(r, desc) for r in rows]
                print(f"  Migrating {len(goals)} goals...")
                for goal in goals:
                    target_date = None
                    if goal.get("deadline"):
                        try:
                            target_date = datetime.fromisoformat(goal["deadline"]).date()
                        except Exception:
                            pass
                    obj = Objective(
                        user_id=user.id,
                        title=goal["title"],
                        description=goal.get("vision"),
                        category=map_category(None),
                        status="completed" if goal.get("status") == "completed" else "active",
                        target_date=target_date,
                    )
                    session.add(obj)
                    await session.flush()
                    goal_id_map[goal["id"]] = obj.id
                    print(f"    ✓ {obj.title}")
            except Exception as e:
                print(f"  goals error: {e}")

            # tasks → tasks
            try:
                async with db.execute("SELECT * FROM tasks WHERE is_deleted = 0") as cursor:
                    desc = cursor.description
                    rows = await cursor.fetchall()
                tasks_data = [row_to_dict(r, desc) for r in rows]
                print(f"  Migrating {len(tasks_data)} tasks...")
                status_map = {"done": "done", "completed": "done", "open": "todo", "in_progress": "in_progress"}
                for t in tasks_data:
                    raw_status = (t.get("status") or "open").lower()
                    status = status_map.get(raw_status, "todo")
                    due_date = None
                    if t.get("deadline"):
                        try:
                            due_date = datetime.fromisoformat(t["deadline"]).date()
                        except Exception:
                            pass
                    task = Task(
                        user_id=user.id,
                        title=t["title"],
                        description=t.get("note"),
                        status=status,
                        priority=3,
                        due_date=due_date,
                    )
                    session.add(task)
                    print(f"    ✓ {task.title} [{status}]")
                await session.flush()
            except Exception as e:
                print(f"  tasks error: {e}")

            # entries → logs
            try:
                async with db.execute("SELECT * FROM entries WHERE is_deleted = 0 ORDER BY created_at") as cursor:
                    desc = cursor.description
                    rows = await cursor.fetchall()
                entries = [row_to_dict(r, desc) for r in rows]
                print(f"  Migrating {len(entries)} entries...")
                count = 0
                for entry in entries:
                    activity = (entry.get("activity") or "").lower()
                    if entry.get("mood_score"):
                        log_type = "mood"
                    elif activity in ("workout", "exercise", "training", "gym"):
                        log_type = "workout"
                    elif activity in ("water", "trinken"):
                        log_type = "water"
                    else:
                        log_type = "general"

                    data = {}
                    if entry.get("activity"):
                        data["activity"] = entry["activity"]
                    if entry.get("value") is not None:
                        data["value"] = entry["value"]
                    if entry.get("unit"):
                        data["unit"] = entry["unit"]
                    if entry.get("mood_score"):
                        data["mood_score"] = entry["mood_score"]
                    if entry.get("note"):
                        data["note"] = entry["note"]
                    if entry.get("tags"):
                        data["tags"] = entry["tags"]

                    logged_at = datetime.utcnow()
                    if entry.get("created_at"):
                        try:
                            logged_at = datetime.fromisoformat(entry["created_at"])
                        except Exception:
                            pass

                    log = Log(
                        user_id=user.id,
                        log_type=log_type,
                        data=data,
                        raw_input=entry.get("raw_message") or entry.get("note"),
                        source="migrated",
                        logged_at=logged_at,
                    )
                    session.add(log)
                    count += 1
                    print(f"    ✓ {log_type}: {entry.get('activity') or entry.get('note', '')[:40]}")
                await session.flush()
            except Exception as e:
                print(f"  entries error: {e}")

        await session.commit()
        print(f"\n✅ Migration complete!")
        print(f"  Objectives: {len(area_id_map)} (areas) + {len(goal_id_map)} (goals)")
        print(f"  Tasks: {len(tasks_data) if 'tasks_data' in dir() else '?'}")
        print(f"  Logs: {count if 'count' in dir() else '?'}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python migrate_cloudbrain.py <telegram_id>")
        print("Example: python migrate_cloudbrain.py 123456789")
        sys.exit(1)
    asyncio.run(migrate(int(sys.argv[1])))
