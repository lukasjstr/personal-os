"""Phase B3 — Add objective_task_suggestions table

Revision ID: 012
Revises: 011
Create Date: 2026-03-05 00:00:00.000000

Adds:
- objective_task_suggestions: persists AI-generated task suggestions for objectives
  Status: pending → accepted | rejected
  Accepted suggestions create a real Task row (accepted_task_id FK).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "012"
down_revision: Union[str, None] = "011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS objective_task_suggestions (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            objective_id INTEGER NOT NULL REFERENCES objectives(id) ON DELETE CASCADE,
            title VARCHAR(500) NOT NULL,
            description TEXT,
            priority INTEGER NOT NULL DEFAULT 3,
            reason TEXT,
            status VARCHAR(20) NOT NULL DEFAULT 'pending',
            accepted_task_id INTEGER REFERENCES tasks(id) ON DELETE SET NULL,
            created_at TIMESTAMP DEFAULT now(),
            updated_at TIMESTAMP
        )
    """))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_obj_task_sugg_user_id "
        "ON objective_task_suggestions (user_id)"
    ))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_obj_task_sugg_objective_id "
        "ON objective_task_suggestions (objective_id)"
    ))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_obj_task_sugg_status "
        "ON objective_task_suggestions (status)"
    ))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("DROP TABLE IF EXISTS objective_task_suggestions"))
