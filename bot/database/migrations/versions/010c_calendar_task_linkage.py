"""B4 — Calendar task linkage index

Revision ID: 010c
Revises: 010b
Create Date: 2026-03-05 00:00:00.000000

Adds:
- Index on calendar_events(linked_task_id) for fast task↔event lookups.
  The FK column itself has existed since migration 001; this migration only
  materialises the index that was omitted from the original schema.

NOTE: Was originally filed as duplicate revision "010". Renumbered to "010c"
during Epic 3.1 alembic hygiene (2026-03-13).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "010c"
down_revision: Union[str, None] = "010b"
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
