"""Phase 5.3 — Fitness Splits

Revision ID: 004
Revises: 003
Create Date: 2026-03-02 00:00:00.000000

Adds:
- fitness_splits table: id, user_id, name, exercises (JSONB), day_of_week,
  order_in_rotation, created_at
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS fitness_splits (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            exercises JSONB NOT NULL DEFAULT '[]',
            day_of_week INTEGER,
            order_in_rotation INTEGER,
            created_at TIMESTAMP DEFAULT now()
        )
    """))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_fitness_splits_user_id ON fitness_splits(user_id)"
    ))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("DROP INDEX IF EXISTS ix_fitness_splits_user_id"))
    conn.execute(sa.text("DROP TABLE IF EXISTS fitness_splits"))
