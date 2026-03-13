"""Epic 3.1 — Apply missing calendar_events index on production

Revision ID: 020
Revises: 019
Create Date: 2026-03-13

Context:
  Migration 010c (calendar task linkage index) was created during alembic hygiene
  cleanup (Epic 3.1). The index it defines was never applied to the production
  database because the original 010_calendar_task_linkage.py file had a duplicate
  revision ID that Alembic silently skipped.

  This migration ensures the index exists on any database that was already at
  revision 019 when the hygiene fix was applied. It is a no-op if the index
  already exists.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "020"
down_revision: Union[str, None] = "019"
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
