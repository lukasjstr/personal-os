"""Phase B5 — Routine-Objective Impact Scoring

Revision ID: 010b
Revises: 010
Create Date: 2026-03-05 00:00:00.000000

Adds:
- routine_objective_impacts table: M2M link between routines and objectives
  with an integer impact_score (1–5) and optional notes.
  Safe defaults; existing rows unaffected.

NOTE: Was originally filed as duplicate revision "010". Renumbered to "010b"
during Epic 3.1 alembic hygiene (2026-03-13).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "010b"
down_revision: Union[str, None] = "010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS routine_objective_impacts (
            id          SERIAL PRIMARY KEY,
            user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            routine_id  INTEGER NOT NULL REFERENCES routines(id) ON DELETE CASCADE,
            objective_id INTEGER NOT NULL REFERENCES objectives(id) ON DELETE CASCADE,
            impact_score INTEGER NOT NULL DEFAULT 3 CHECK (impact_score BETWEEN 1 AND 5),
            notes       TEXT,
            created_at  TIMESTAMP DEFAULT now(),
            updated_at  TIMESTAMP,
            UNIQUE (routine_id, objective_id)
        )
    """))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_roi_user_id      ON routine_objective_impacts (user_id)"
    ))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_roi_routine_id   ON routine_objective_impacts (routine_id)"
    ))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_roi_objective_id ON routine_objective_impacts (objective_id)"
    ))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("DROP TABLE IF EXISTS routine_objective_impacts"))
