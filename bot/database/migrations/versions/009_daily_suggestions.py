"""Phase 8.2 — Add daily_suggestions table

Revision ID: 009
Revises: 008
Create Date: 2026-03-02 00:00:00.000000

Adds:
- daily_suggestions table: stores AI-generated daily coaching suggestions per user per day
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS daily_suggestions (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            date DATE NOT NULL,
            suggestions JSONB NOT NULL,
            created_at TIMESTAMP DEFAULT now(),
            UNIQUE(user_id, date)
        )
    """))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_daily_suggestions_user_id ON daily_suggestions (user_id)"
    ))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("DROP TABLE IF EXISTS daily_suggestions"))
