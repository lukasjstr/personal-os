"""Phase A3 — Add action_queue_items table

Revision ID: 011
Revises: 010
Create Date: 2026-03-05 00:00:00.000000

Adds:
- action_queue_items table: persists autopilot action queue entries with state transitions
  States: planned → suggested → accepted → completed | snoozed
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "011"
down_revision: Union[str, None] = "010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS action_queue_items (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            state VARCHAR(20) NOT NULL DEFAULT 'planned',
            item_type VARCHAR(30) NOT NULL DEFAULT 'task',
            title VARCHAR(500) NOT NULL,
            description TEXT,
            reason TEXT,
            linked_task_id INTEGER REFERENCES tasks(id) ON DELETE SET NULL,
            snoozed_until TIMESTAMP,
            created_at TIMESTAMP DEFAULT now(),
            updated_at TIMESTAMP
        )
    """))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_action_queue_items_user_id "
        "ON action_queue_items (user_id)"
    ))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_action_queue_items_state "
        "ON action_queue_items (state)"
    ))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("DROP TABLE IF EXISTS action_queue_items"))
