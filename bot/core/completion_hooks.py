"""CORE-7 completion hooks — KR/objective progress updates + next-action surfacing.

Epic 1.2: get_next_unblocked_action is now graph-aware:
- Excludes tasks blocked via NodeRelation (blocks / depends_on relation types)
- Prefers tasks that unlock downstream work (unlocks edges)
- Prefers tasks linked to active objectives via contributes_to edges
- Returns explainability metadata: why_selected, blocked_by, unlocks_count, contributes_to
- Deterministic fallback when relation data is absent
"""
from collections import defaultdict
from datetime import date
from typing import Optional

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.core.explainability import get_task_reason
from bot.database.models import KeyResult, NodeRelation, Objective, Routine, Task


async def update_kr_on_task_complete(
    session: AsyncSession,
    task: Task,
) -> Optional[KeyResult]:
    """Increment KR current_value when a linked task is completed.

    Strategy per metric_type:
    - checklist / number: +1
    - boolean: set to 1.0 (done)
    - percentage: recalculate from done/total tasks on this KR
    - streak: no-op (streaks driven by routine completions)
    """
    if not task.key_result_id:
        return None

    result = await session.execute(
        select(KeyResult).where(KeyResult.id == task.key_result_id)
    )
    kr = result.scalar_one_or_none()
    if not kr or kr.status != "active":
        return None

    if kr.metric_type in ("checklist", "number"):
        kr.current_value = (kr.current_value or 0.0) + 1.0
    elif kr.metric_type == "boolean":
        kr.current_value = 1.0
    elif kr.metric_type == "percentage":
        total_res = await session.execute(
            select(func.count()).select_from(Task).where(Task.key_result_id == kr.id)
        )
        done_res = await session.execute(
            select(func.count()).select_from(Task).where(
                and_(Task.key_result_id == kr.id, Task.status == "done")
            )
        )
        total = total_res.scalar() or 1
        done = done_res.scalar() or 0
        kr.current_value = round((done / total) * 100.0, 1)
    # streak: driven by routine completions, skip here

    if kr.target_value and kr.current_value >= kr.target_value and kr.status == "active":
        kr.status = "completed"

    await session.flush()
    return kr


async def update_kr_on_routine_complete(
    session: AsyncSession,
    routine: Routine,
) -> Optional[KeyResult]:
    """Increment KR current_value when a linked routine is completed.

    Applies to all metric_types that a routine might drive (streak, number, checklist).
    """
    if not routine.linked_key_result_id:
        return None

    result = await session.execute(
        select(KeyResult).where(KeyResult.id == routine.linked_key_result_id)
    )
    kr = result.scalar_one_or_none()
    if not kr or kr.status != "active":
        return None

    kr.current_value = (kr.current_value or 0.0) + 1.0

    if kr.target_value and kr.current_value >= kr.target_value and kr.status == "active":
        kr.status = "completed"

    await session.flush()
    return kr


async def check_objective_auto_complete(
    session: AsyncSession,
    objective_id: int,
) -> bool:
    """Mark objective completed if all its active KRs have reached their target.

    Returns True if the objective was just completed, False otherwise.
    """
    obj_res = await session.execute(
        select(Objective).where(Objective.id == objective_id)
    )
    obj = obj_res.scalar_one_or_none()
    if not obj or obj.status != "active":
        return False

    kr_res = await session.execute(
        select(KeyResult).where(
            and_(KeyResult.objective_id == objective_id, KeyResult.status.in_(["active", "completed"]))
        )
    )
    krs = kr_res.scalars().all()
    if not krs:
        return False

    all_done = all(
        kr.status == "completed"
        or (kr.target_value is not None and kr.current_value >= kr.target_value)
        for kr in krs
    )
    if all_done:
        obj.status = "completed"
        await session.flush()
        return True
    return False


async def get_next_unblocked_action(
    session: AsyncSession,
    user_id: int,
    completed_task: Optional[Task] = None,
) -> Optional[dict]:
    """Return the highest-priority next unblocked task as a dict.

    Epic 1.2 — Graph-aware selection:
    - Excludes tasks blocked by NodeRelation (blocks / depends_on)
    - Scores remaining tasks by graph impact: unlocks_count, contributes_to
    - Returns explainability metadata: why_selected, blocked_by, unlocks_count, contributes_to
    - Deterministic fallback when no relation data or all tasks are blocked

    Priority order when completed_task provided:
    1. Graph-scored unblocked task in the same Key Result
    2. Graph-scored unblocked task in the same Objective
    3. Global top graph-scored unblocked task

    Backward compatibility: all previously present fields are still returned.
    """
    today = date.today()

    def _task_dict(t: Task, source: str, graph_meta: Optional[dict] = None) -> dict:
        base = {
            "id": t.id,
            "title": t.title,
            "priority": t.priority,
            "due_date": t.due_date.isoformat() if t.due_date else None,
            "key_result_id": t.key_result_id,
            "objective_id": t.objective_id,
            "source": source,
            "reason": get_task_reason(t),
            # Epic 1.2 explainability fields
            "why_selected": "",
            "blocked_by": [],
            "unlocks_count": 0,
            "contributes_to": [],
        }
        if graph_meta:
            base.update(graph_meta)
        return base

    # ── 1. Load all open candidate tasks ──────────────────────────────────────
    cand_res = await session.execute(
        select(Task)
        .where(and_(
            Task.user_id == user_id,
            Task.status.in_(["todo", "in_progress"]),
            Task.category != "shopping",
            Task.blocked_by_task_id.is_(None),  # legacy hard-block field
        ))
        .order_by(Task.priority.asc(), Task.due_date.asc().nulls_last(), Task.created_at.asc())
    )
    candidates: list[Task] = list(cand_res.scalars().all())
    if not candidates:
        return None

    task_id_set: set[int] = {t.id for t in candidates}
    task_by_id: dict[int, Task] = {t.id: t for t in candidates}

    # ── 2. Load NodeRelation rows involving these tasks ────────────────────────
    if task_id_set:
        rel_res = await session.execute(
            select(NodeRelation).where(
                and_(
                    NodeRelation.user_id == user_id,
                    or_(
                        and_(
                            NodeRelation.from_type == "task",
                            NodeRelation.from_id.in_(list(task_id_set)),
                        ),
                        and_(
                            NodeRelation.to_type == "task",
                            NodeRelation.to_id.in_(list(task_id_set)),
                        ),
                    ),
                )
            )
        )
        all_rels: list[NodeRelation] = list(rel_res.scalars().all())
    else:
        all_rels = []

    # ── 3. Collect external blocker task IDs (not in candidates) ──────────────
    external_blocker_ids: set[int] = set()
    for rel in all_rels:
        if rel.relation_type in ("blocks", "depends_on"):
            if rel.from_type == "task" and rel.from_id not in task_id_set:
                external_blocker_ids.add(rel.from_id)
            if rel.to_type == "task" and rel.to_id not in task_id_set:
                external_blocker_ids.add(rel.to_id)

    external_statuses: dict[int, str] = {}
    if external_blocker_ids:
        ext_res = await session.execute(
            select(Task.id, Task.status).where(Task.id.in_(list(external_blocker_ids)))
        )
        for row in ext_res:
            external_statuses[row[0]] = row[1]

    def _is_done(task_id: int) -> bool:
        """True if the referenced task is done (not an open candidate)."""
        if task_id in task_id_set:
            return False  # open candidates are not done
        # External: default to done if not found (optimistic — don't over-block)
        return external_statuses.get(task_id, "done") == "done"

    # ── 4. Build per-task relation indices ────────────────────────────────────
    # inbound_blocks[task_id]   → list of (from_type, from_id) that block this task
    # outbound_depends_on[task_id] → list of (to_type, to_id) this task depends on
    # outbound_unlocks[task_id] → count of nodes this task unlocks
    # outbound_contributes[task_id] → list of (to_type, to_id) dicts
    inbound_blocks: dict[int, list[tuple[str, int]]] = defaultdict(list)
    outbound_depends_on: dict[int, list[tuple[str, int]]] = defaultdict(list)
    outbound_unlocks: dict[int, int] = defaultdict(int)
    outbound_contributes: dict[int, list[tuple[str, int]]] = defaultdict(list)

    for rel in all_rels:
        if rel.relation_type == "blocks":
            # rel.from blocks rel.to → to_task is blocked if from is not done
            if rel.to_type == "task" and rel.to_id in task_id_set:
                inbound_blocks[rel.to_id].append((rel.from_type, rel.from_id))
        elif rel.relation_type == "depends_on":
            # rel.from depends_on rel.to → from_task is blocked if to is not done
            if rel.from_type == "task" and rel.from_id in task_id_set:
                outbound_depends_on[rel.from_id].append((rel.to_type, rel.to_id))
        elif rel.relation_type == "unlocks":
            if rel.from_type == "task" and rel.from_id in task_id_set:
                outbound_unlocks[rel.from_id] += 1
        elif rel.relation_type == "contributes_to":
            if rel.from_type == "task" and rel.from_id in task_id_set:
                outbound_contributes[rel.from_id].append((rel.to_type, rel.to_id))

    # ── 5. Filter: retain only graph-unblocked tasks ──────────────────────────
    def _graph_blockers(task_id: int) -> list[dict]:
        """Return list of blocking node refs; empty means unblocked."""
        blockers: list[dict] = []
        # Inbound blocks: Y blocks T → blocked if Y (task) is not done
        for from_type, from_id in inbound_blocks.get(task_id, []):
            if from_type == "task" and not _is_done(from_id):
                blockers.append({"type": from_type, "id": from_id})
        # Outbound depends_on: T depends_on X → blocked if X (task) is not done
        for to_type, to_id in outbound_depends_on.get(task_id, []):
            if to_type == "task" and not _is_done(to_id):
                blockers.append({"type": to_type, "id": to_id})
        return blockers

    unblocked: list[Task] = []
    for t in candidates:
        if not _graph_blockers(t.id):
            unblocked.append(t)

    # Fallback: if all candidates are graph-blocked, use naive priority ordering
    if not unblocked:
        t = candidates[0]
        unlocks_count = outbound_unlocks.get(t.id, 0)
        contributes_to = [{"type": tp, "id": i} for tp, i in outbound_contributes.get(t.id, [])]
        return _task_dict(t, "fallback_all_blocked", {
            "why_selected": "Fallback: alle Aufgaben blockiert — nächste nach Priorität",
            "blocked_by": _graph_blockers(t.id),
            "unlocks_count": unlocks_count,
            "contributes_to": contributes_to,
        })

    # ── 6. Score unblocked tasks by graph impact ──────────────────────────────
    def _score(task: Task) -> float:
        score = 0.0
        score += outbound_unlocks.get(task.id, 0) * 10.0       # each unlock = +10
        score += len(outbound_contributes.get(task.id, [])) * 5.0  # each contribution = +5
        score += (6 - min(task.priority, 5)) * 3.0             # priority 1 → +15, 5 → +3
        if task.due_date:
            if task.due_date < today:
                score += 20.0   # overdue
            elif task.due_date == today:
                score += 15.0   # due today
            elif (task.due_date - today).days <= 3:
                score += 8.0    # due soon
        return score

    unblocked.sort(key=lambda t: -_score(t))

    # ── 7. Apply contextual preference from completed_task ────────────────────
    selected: Optional[Task] = None
    source = "graph_global"

    if completed_task:
        if completed_task.key_result_id:
            for t in unblocked:
                if t.key_result_id == completed_task.key_result_id:
                    selected = t
                    source = "same_kr"
                    break
        if not selected and completed_task.objective_id:
            for t in unblocked:
                if t.objective_id == completed_task.objective_id:
                    selected = t
                    source = "same_objective"
                    break

    if not selected:
        selected = unblocked[0]

    # ── 8. Build explainability metadata ──────────────────────────────────────
    unlocks_count = outbound_unlocks.get(selected.id, 0)
    contributes_to = [{"type": tp, "id": i} for tp, i in outbound_contributes.get(selected.id, [])]

    if source in ("same_kr", "same_objective"):
        why_selected = "Gleicher Kontext wie abgeschlossene Aufgabe"
    elif unlocks_count > 0:
        noun = "Aufgabe" if unlocks_count == 1 else "Aufgaben"
        why_selected = f"Schaltet {unlocks_count} weitere {noun} frei"
    elif contributes_to:
        why_selected = "Trägt zu aktivem Ziel bei"
    elif selected.due_date and selected.due_date < today:
        n = (today - selected.due_date).days
        why_selected = f"Überfällig seit {n} {'Tag' if n == 1 else 'Tagen'}"
    elif selected.due_date and selected.due_date == today:
        why_selected = "Heute fällig"
    elif selected.priority == 1:
        why_selected = "Höchste Priorität"
    else:
        why_selected = "Nächste offene Aufgabe"

    return _task_dict(selected, source, {
        "why_selected": why_selected,
        "blocked_by": [],  # selected task is unblocked
        "unlocks_count": unlocks_count,
        "contributes_to": contributes_to,
    })
