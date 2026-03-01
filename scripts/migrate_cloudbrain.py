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
        # Get target user
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        if not user:
            print(f"ERROR: User with telegram_id={telegram_id} not found in DB. Create user first.")
            sys.exit(1)

        print(f"Migrating to user #{user.id} ({user.first_name})")

        async with aiosqlite.connect(CLOUDBRAIN_DB) as db:
            db.row_factory = aiosqlite.Row

            # Migrate life_areas → objectives
            area_id_map: dict[int, int] = {}  # old_id → new objective_id
            try:
                async with db.execute("SELECT * FROM life_areas") as cursor:
                    areas = await cursor.fetchall()
                print(f"  Migrating {len(areas)} life areas...")
                for area in areas:
                    obj = Objective(
                        user_id=user.id,
                        title=area["name"] if "name" in area.keys() else area["title"],
                        description=area.get("description"),
                        category=map_category(area.get("category") or area.get("name")),
                        status="active",
                    )
                    session.add(obj)
                    await session.flush()
                    area_id_map[area["id"]] = obj.id
            except Exception as e:
                print(f"  life_areas: {e}")

            # Migrate goals → objectives
            goal_id_map: dict[int, int] = {}
            try:
                async with db.execute("SELECT * FROM goals") as cursor:
                    goals = await cursor.fetchall()
                print(f"  Migrating {len(goals)} goals...")
                for goal in goals:
                    try:
                        target_date = None
                        if goal.get("deadline") or goal.get("target_date"):
                            raw = goal.get("deadline") or goal.get("target_date")
                            try:
                                target_date = datetime.fromisoformat(str(raw)).date()
                            except Exception:
                                pass
                        obj = Objective(
                            user_id=user.id,
                            title=goal["title"] if "title" in goal.keys() else goal["name"],
                            description=goal.get("description"),
                            category=map_category(goal.get("category")),
                            status="active" if not goal.get("completed") else "completed",
                            target_date=target_date,
                        )
                        session.add(obj)
                        await session.flush()
                        goal_id_map[goal["id"]] = obj.id
                    except Exception as e:
                        print(f"    goal #{goal['id']} error: {e}")
            except Exception as e:
                print(f"  goals: {e}")

            # Migrate tasks → tasks
            try:
                async with db.execute("SELECT * FROM tasks") as cursor:
                    tasks = await cursor.fetchall()
                print(f"  Migrating {len(tasks)} tasks...")
                for t in tasks:
                    try:
                        status_map = {
                            "done": "done", "completed": "done",
                            "in_progress": "in_progress", "active": "in_progress",
                            "todo": "todo", "pending": "todo",
                        }
                        raw_status = (t.get("status") or "todo").lower()
                        status = status_map.get(raw_status, "todo")

                        due_date = None
                        if t.get("due_date") or t.get("deadline"):
                            raw = t.get("due_date") or t.get("deadline")
                            try:
                                due_date = datetime.fromisoformat(str(raw)).date()
                            except Exception:
                                pass

                        completed_at = None
                        if status == "done" and t.get("completed_at"):
                            try:
                                completed_at = datetime.fromisoformat(str(t["completed_at"]))
                            except Exception:
                                completed_at = datetime.utcnow()

                        task = Task(
                            user_id=user.id,
                            title=t["title"] if "title" in t.keys() else t["name"],
                            description=t.get("description"),
                            status=status,
                            priority=t.get("priority", 3) or 3,
                            due_date=due_date,
                            completed_at=completed_at,
                        )
                        session.add(task)
                    except Exception as e:
                        print(f"    task #{t['id']} error: {e}")
                await session.flush()
            except Exception as e:
                print(f"  tasks: {e}")

            # Migrate entries → logs
            try:
                async with db.execute("SELECT * FROM entries ORDER BY created_at") as cursor:
                    entries = await cursor.fetchall()
                print(f"  Migrating {len(entries)} entries...")
                count = 0
                for entry in entries:
                    try:
                        entry_type = (entry.get("type") or entry.get("entry_type") or "note").lower()
                        log_type_map = {
                            "workout": "workout", "exercise": "workout",
                            "water": "water", "hydration": "water",
                            "mood": "mood", "feeling": "mood",
                            "food": "food", "meal": "food",
                            "note": "note", "journal": "note",
                            "progress": "progress",
                        }
                        log_type = log_type_map.get(entry_type, "general")

                        data: dict = {}
                        if entry.get("data"):
                            try:
                                data = json.loads(entry["data"]) if isinstance(entry["data"], str) else dict(entry["data"])
                            except Exception:
                                data = {"content": str(entry["data"])}
                        if not data:
                            content = entry.get("content") or entry.get("text") or entry.get("body") or ""
                            data = {"content": str(content)}

                        logged_at = datetime.utcnow()
                        for ts_field in ("created_at", "logged_at", "date"):
                            if entry.get(ts_field):
                                try:
                                    logged_at = datetime.fromisoformat(str(entry[ts_field]))
                                    break
                                except Exception:
                                    pass

                        log = Log(
                            user_id=user.id,
                            log_type=log_type,
                            data=data,
                            raw_input=entry.get("content") or entry.get("text"),
                            source="migrated",
                            logged_at=logged_at,
                        )
                        session.add(log)
                        count += 1
                    except Exception as e:
                        print(f"    entry #{entry['id']} error: {e}")

                await session.flush()
                print(f"    Migrated {count} entries")
            except Exception as e:
                print(f"  entries: {e}")

        await session.commit()
        print("\nMigration complete!")
        print(f"Objectives: {len(area_id_map) + len(goal_id_map)}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python migrate_cloudbrain.py <telegram_id>")
        print("Example: python migrate_cloudbrain.py 123456789")
        sys.exit(1)
    asyncio.run(migrate(int(sys.argv[1])))
