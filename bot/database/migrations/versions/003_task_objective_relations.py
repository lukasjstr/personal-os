"""Phase 5.1 — Task-Objective deep relations

Revision ID: 003
Revises: 002
Create Date: 2026-03-02 00:00:00.000000

Adds:
- tasks.objective_id         FK → objectives (nullable, direct link)
- tasks.parent_task_id       FK → tasks (nullable, sub-task hierarchy)
- tasks.blocked_by_task_id   FK → tasks (nullable, dependency blocking)
- objectives.parent_objective_id FK → objectives (nullable, Goal → Sub-Objective)
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # ── tasks: direct objective link ───────────────────────────────────────────
    conn.execute(sa.text(
        "ALTER TABLE tasks ADD COLUMN IF NOT EXISTS objective_id INTEGER REFERENCES objectives(id) ON DELETE SET NULL"
    ))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_tasks_objective_id ON tasks(objective_id)"
    ))

    # ── tasks: sub-task hierarchy ──────────────────────────────────────────────
    conn.execute(sa.text(
        "ALTER TABLE tasks ADD COLUMN IF NOT EXISTS parent_task_id INTEGER REFERENCES tasks(id) ON DELETE SET NULL"
    ))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_tasks_parent_task_id ON tasks(parent_task_id)"
    ))

    # ── tasks: dependency blocking ─────────────────────────────────────────────
    conn.execute(sa.text(
        "ALTER TABLE tasks ADD COLUMN IF NOT EXISTS blocked_by_task_id INTEGER REFERENCES tasks(id) ON DELETE SET NULL"
    ))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_tasks_blocked_by_task_id ON tasks(blocked_by_task_id)"
    ))

    # ── objectives: parent objective (Goal → Sub-Objective) ───────────────────
    conn.execute(sa.text(
        "ALTER TABLE objectives ADD COLUMN IF NOT EXISTS parent_objective_id INTEGER REFERENCES objectives(id) ON DELETE SET NULL"
    ))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_objectives_parent_objective_id ON objectives(parent_objective_id)"
    ))


def downgrade() -> None:
    conn = op.get_bind()

    conn.execute(sa.text("DROP INDEX IF EXISTS ix_objectives_parent_objective_id"))
    conn.execute(sa.text("ALTER TABLE objectives DROP COLUMN IF EXISTS parent_objective_id"))

    conn.execute(sa.text("DROP INDEX IF EXISTS ix_tasks_blocked_by_task_id"))
    conn.execute(sa.text("ALTER TABLE tasks DROP COLUMN IF EXISTS blocked_by_task_id"))

    conn.execute(sa.text("DROP INDEX IF EXISTS ix_tasks_parent_task_id"))
    conn.execute(sa.text("ALTER TABLE tasks DROP COLUMN IF EXISTS parent_task_id"))

    conn.execute(sa.text("DROP INDEX IF EXISTS ix_tasks_objective_id"))
    conn.execute(sa.text("ALTER TABLE tasks DROP COLUMN IF EXISTS objective_id"))
