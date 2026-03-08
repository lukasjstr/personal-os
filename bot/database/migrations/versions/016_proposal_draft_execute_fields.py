"""P0.4 — Add executed_at + executed_objective_id to okr_proposal_drafts

Revision ID: 016
Revises: 015
Create Date: 2026-03-08 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "016"
down_revision: Union[str, None] = "015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("""
        ALTER TABLE okr_proposal_drafts
            ADD COLUMN IF NOT EXISTS executed_at TIMESTAMP,
            ADD COLUMN IF NOT EXISTS executed_objective_id INTEGER REFERENCES objectives(id) ON DELETE SET NULL;
    """))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("""
        ALTER TABLE okr_proposal_drafts
            DROP COLUMN IF EXISTS executed_at,
            DROP COLUMN IF EXISTS executed_objective_id;
    """))
