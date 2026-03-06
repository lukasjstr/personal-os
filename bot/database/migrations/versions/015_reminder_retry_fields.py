"""CORE-5c — Add retry_count + next_retry_at to scheduled_reminders

Revision ID: 015
Revises: 014
Create Date: 2026-03-06 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "015"
down_revision: Union[str, None] = "014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("""
        ALTER TABLE scheduled_reminders
            ADD COLUMN IF NOT EXISTS retry_count INTEGER NOT NULL DEFAULT 0,
            ADD COLUMN IF NOT EXISTS next_retry_at TIMESTAMP;
    """))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("""
        ALTER TABLE scheduled_reminders
            DROP COLUMN IF EXISTS retry_count,
            DROP COLUMN IF EXISTS next_retry_at;
    """))
