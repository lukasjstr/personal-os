"""Phase 5.4 — Routine time-of-day groups and shopping defaults

Revision ID: 005
Revises: 004
Create Date: 2026-03-02 00:00:00.000000

Adds:
- routines.time_of_day TEXT (morning/midday/evening/anytime)
- routines.sort_order INTEGER
- shopping_defaults table: id, user_id, title, category, active, created_at
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # Add columns to routines
    conn.execute(sa.text(
        "ALTER TABLE routines ADD COLUMN IF NOT EXISTS time_of_day TEXT DEFAULT 'anytime'"
    ))
    conn.execute(sa.text(
        "ALTER TABLE routines ADD COLUMN IF NOT EXISTS sort_order INTEGER DEFAULT 0"
    ))

    # Create shopping_defaults table
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS shopping_defaults (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            title TEXT NOT NULL,
            category TEXT,
            active BOOLEAN DEFAULT true,
            created_at TIMESTAMP DEFAULT now()
        )
    """))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_shopping_defaults_user_id ON shopping_defaults(user_id)"
    ))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("DROP INDEX IF EXISTS ix_shopping_defaults_user_id"))
    conn.execute(sa.text("DROP TABLE IF EXISTS shopping_defaults"))
    conn.execute(sa.text("ALTER TABLE routines DROP COLUMN IF EXISTS time_of_day"))
    conn.execute(sa.text("ALTER TABLE routines DROP COLUMN IF EXISTS sort_order"))
