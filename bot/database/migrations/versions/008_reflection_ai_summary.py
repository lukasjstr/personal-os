"""Phase 8.1 — Add ai_summary and week_score to weekly_reflections

Revision ID: 008
Revises: 007
Create Date: 2026-03-02 00:00:00.000000

Adds:
- weekly_reflections.week_score INTEGER (user self-rating 1-10)
- weekly_reflections.ai_summary JSONB (AI-generated summary with recommendations)
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text(
        "ALTER TABLE weekly_reflections ADD COLUMN IF NOT EXISTS week_score INTEGER"
    ))
    conn.execute(sa.text(
        "ALTER TABLE weekly_reflections ADD COLUMN IF NOT EXISTS ai_summary JSONB"
    ))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("ALTER TABLE weekly_reflections DROP COLUMN IF EXISTS ai_summary"))
    conn.execute(sa.text("ALTER TABLE weekly_reflections DROP COLUMN IF EXISTS week_score"))
