"""Script to organize unassigned tasks into objectives using GPT-4o.

Usage (standalone):
    python -m bot.scripts.organize_data [--user-id <id>]

Telegram command:
    /organize  →  triggers organize_user_data() for the calling user
"""
from __future__ import annotations

import asyncio
import json
import logging
import sys
from datetime import datetime

from openai import AsyncOpenAI
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import settings
from bot.database.connection import get_session
from bot.database.models import Objective, Task, User

logger = logging.getLogger(__name__)
openai_client = AsyncOpenAI(api_key=settings.openai_api_key)


# ─── Core logic ───────────────────────────────────────────────────────────────

async def organize_user_data(session: AsyncSession, user: User) -> dict:
    """
    1. Load all tasks without an objective_id.
    2. Load all objectives for the user.
    3. GPT-4o assigns each orphaned task to an existing objective or proposes a new one.
    4. Objectives with no tasks get 3 suggested tasks.
    Returns a report dict with counts and details.
    """
    report: dict = {
        "user_id": user.id,
        "orphaned_tasks_assigned": 0,
        "new_objectives_created": 0,
        "suggested_tasks_added": 0,
        "details": [],
    }

    # ── 1. Load orphaned tasks ──────────────────────────────────────────────
    orphan_result = await session.execute(
        select(Task).where(
            and_(
                Task.user_id == user.id,
                Task.objective_id.is_(None),
                Task.category != "shopping",
                Task.status != "done",
            )
        )
    )
    orphaned_tasks = orphan_result.scalars().all()

    # ── 2. Load objectives ──────────────────────────────────────────────────
    obj_result = await session.execute(
        select(Objective).where(Objective.user_id == user.id)
    )
    objectives = obj_result.scalars().all()

    if not orphaned_tasks and not objectives:
        report["details"].append("No data to organize.")
        return report

    # ── 3. Assign orphaned tasks to objectives via GPT ──────────────────────
    if orphaned_tasks:
        assignments = await _assign_tasks_to_objectives(orphaned_tasks, objectives)

        # Track newly created objectives by title to avoid duplicates
        new_obj_map: dict[str, Objective] = {}

        for task, assignment in zip(orphaned_tasks, assignments):
            obj_id = assignment.get("objective_id")
            new_title = assignment.get("new_objective_title")

            if obj_id:
                # Assign to existing objective
                matched = next((o for o in objectives if o.id == obj_id), None)
                if matched:
                    task.objective_id = matched.id
                    report["orphaned_tasks_assigned"] += 1
                    report["details"].append(
                        f"Task '{task.title}' → Objective '{matched.title}'"
                    )
            elif new_title:
                # Create or reuse a new objective
                if new_title in new_obj_map:
                    new_obj = new_obj_map[new_title]
                else:
                    category = assignment.get("new_objective_category", "general")
                    new_obj = Objective(
                        user_id=user.id,
                        title=new_title,
                        description=assignment.get("new_objective_description", ""),
                        category=category,
                        status="active",
                        priority_weight=5,
                    )
                    session.add(new_obj)
                    await session.flush()  # get id
                    objectives = list(objectives) + [new_obj]
                    new_obj_map[new_title] = new_obj
                    report["new_objectives_created"] += 1
                    report["details"].append(f"Created new Objective: '{new_title}'")

                task.objective_id = new_obj.id
                report["orphaned_tasks_assigned"] += 1
                report["details"].append(
                    f"Task '{task.title}' → New Objective '{new_title}'"
                )

    await session.flush()

    # ── 4. Suggest tasks for empty objectives ───────────────────────────────
    # Reload tasks per objective after assignments
    task_counts: dict[int, int] = {}
    for obj in objectives:
        count_result = await session.execute(
            select(Task).where(
                and_(Task.user_id == user.id, Task.objective_id == obj.id, Task.status != "done")
            )
        )
        task_counts[obj.id] = len(count_result.scalars().all())

    empty_objectives = [o for o in objectives if task_counts.get(o.id, 0) == 0]

    if empty_objectives:
        suggested = await _suggest_tasks_for_objectives(empty_objectives)
        for obj, task_titles in suggested:
            for title in task_titles:
                new_task = Task(
                    user_id=user.id,
                    title=title,
                    objective_id=obj.id,
                    priority=3,
                    status="todo",
                )
                session.add(new_task)
                report["suggested_tasks_added"] += 1
                report["details"].append(
                    f"Suggested task '{title}' for Objective '{obj.title}'"
                )

    await session.flush()
    return report


# ─── GPT helpers ──────────────────────────────────────────────────────────────

BATCH_SIZE = 25  # Process tasks in chunks to stay within token limits


async def _assign_tasks_batch(
    tasks: list[Task], objectives: list[Objective]
) -> list[dict]:
    """Process a single batch of tasks (max BATCH_SIZE) via GPT-4o."""
    obj_list = [
        {"id": o.id, "title": o.title, "category": o.category}
        for o in objectives
    ]
    task_list = [{"id": t.id, "title": t.title} for t in tasks]

    prompt = f"""Du bist ein persönlicher AI-COO. Ordne jeden Task dem semantisch passendsten Objective zu.
Nutze NUR vorhandene Objectives — schlage neue NUR vor, wenn KEIN Objective thematisch passt.

OBJECTIVES:
{json.dumps(obj_list, ensure_ascii=False, indent=2)}

TASKS ({len(task_list)} Stück):
{json.dumps(task_list, ensure_ascii=False, indent=2)}

Antworte mit JSON: {{"assignments": [...]}} — Array in GLEICHER Reihenfolge wie Tasks.
Jedes Element ENTWEDER:
  {{"objective_id": <id>}}
ODER (nur wenn wirklich kein Objective passt):
  {{"new_objective_title": "...", "new_objective_description": "...", "new_objective_category": "health|work|finance|personal|learning|general"}}

WICHTIG: Sei kreativ bei der Zuordnung — Tasks wie 'Slides vorbereiten' gehören zu 'Unterricht/Lehre', nicht zu 'Meditieren'."""

    try:
        response = await openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "Du bist ein intelligenter persönlicher Assistent. Ordne Tasks sinnvoll und semantisch korrekt zu."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=3000,
            temperature=0.2,
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content or "{}"
        data = json.loads(raw)
        # Unwrap {"assignments": [...]} or {"tasks": [...]} or similar
        if isinstance(data, dict):
            for key in ("assignments", "tasks", "results"):
                if key in data and isinstance(data[key], list):
                    data = data[key]
                    break
            else:
                # Last resort: take the first list value
                lists = [v for v in data.values() if isinstance(v, list)]
                data = lists[0] if lists else []
        if isinstance(data, list) and len(data) == len(tasks):
            return data
        logger.warning("GPT returned %d assignments for %d tasks — skipping batch", len(data) if isinstance(data, list) else -1, len(tasks))
    except Exception:
        logger.exception("GPT-4o failed during task assignment batch")

    # Safe fallback: leave all tasks unassigned (better than wrong assignment)
    return [{}] * len(tasks)


async def _assign_tasks_to_objectives(
    tasks: list[Task], objectives: list[Objective]
) -> list[dict]:
    """Assign tasks to objectives in batches of BATCH_SIZE to avoid token limits."""
    all_results: list[dict] = []
    for i in range(0, len(tasks), BATCH_SIZE):
        batch = tasks[i : i + BATCH_SIZE]
        logger.info("Processing batch %d/%d (%d tasks)", i // BATCH_SIZE + 1, (len(tasks) - 1) // BATCH_SIZE + 1, len(batch))
        batch_results = await _assign_tasks_batch(batch, objectives)
        all_results.extend(batch_results)
    return all_results


async def _suggest_tasks_for_objectives(
    objectives: list[Objective],
) -> list[tuple[Objective, list[str]]]:
    """Ask GPT-4o to suggest 3 tasks for each objective without tasks."""
    obj_list = [{"id": o.id, "title": o.title, "description": o.description, "category": o.category} for o in objectives]

    prompt = f"""Du bist ein persönlicher AI-COO. Für folgende Objectives wurden noch keine aktiven Tasks definiert.
Schlage für jedes Objective genau 3 konkrete, umsetzbare Tasks vor (kurze Imperativ-Sätze, max 60 Zeichen).

OBJECTIVES OHNE TASKS:
{json.dumps(obj_list, ensure_ascii=False, indent=2)}

Antworte mit einem JSON-Objekt: {{"<objective_id>": ["task1", "task2", "task3"], ...}}
NUR JSON, kein weiterer Text."""

    results: list[tuple[Objective, list[str]]] = []

    try:
        response = await openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "Du bist ein hilfreicher persönlicher Assistent."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=800,
            temperature=0.5,
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content or "{}"
        data = json.loads(raw)
        for obj in objectives:
            task_titles = data.get(str(obj.id), [])
            if isinstance(task_titles, list):
                results.append((obj, [str(t) for t in task_titles[:3]]))
            else:
                results.append((obj, []))
    except Exception:
        logger.exception("GPT-4o failed during task suggestion")
        for obj in objectives:
            results.append((obj, [f"{obj.title} angehen", f"{obj.title} planen", f"{obj.title} reviewen"]))

    return results


# ─── Standalone entrypoint ────────────────────────────────────────────────────

async def _run_standalone(user_id: int | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    async with get_session() as session:
        if user_id:
            result = await session.execute(select(User).where(User.id == user_id))
            users = result.scalars().all()
        else:
            result = await session.execute(select(User).where(User.is_active == True))  # noqa: E712
            users = result.scalars().all()

        for user in users:
            print(f"\n{'='*60}")
            print(f"Organizing data for user: {user.first_name} (id={user.id})")
            print(f"{'='*60}")
            report = await organize_user_data(session, user)
            print(f"Orphaned tasks assigned: {report['orphaned_tasks_assigned']}")
            print(f"New objectives created:  {report['new_objectives_created']}")
            print(f"Suggested tasks added:   {report['suggested_tasks_added']}")
            print("\nDetails:")
            for line in report["details"]:
                print(f"  • {line}")


if __name__ == "__main__":
    uid: int | None = None
    if "--user-id" in sys.argv:
        idx = sys.argv.index("--user-id")
        if idx + 1 < len(sys.argv):
            uid = int(sys.argv[idx + 1])
    asyncio.run(_run_standalone(uid))
