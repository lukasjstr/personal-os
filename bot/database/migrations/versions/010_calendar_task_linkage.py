"""B4 — Calendar task linkage index

Revision ID: 010
Revises: 009
Create Date: 2026-03-05 00:00:00.000000

Adds:
- Index on calendar_events(linked_task_id) for fast task↔event lookups.
  The FK column itself has existed since migration 001; this migration only
  materialises the index that was omitted from the original schema.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "010"
down_revision: Union[str, None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_calendar_events_linked_task_id "
        "ON calendar_events (linked_task_id)"
    ))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text(
        "DROP INDEX IF EXISTS ix_calendar_events_linked_task_id"
    ))
