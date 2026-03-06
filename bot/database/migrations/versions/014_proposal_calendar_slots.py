"""CORE-3A — Add proposal_calendar_slots table

Revision ID: 014
Revises: 013
Create Date: 2026-03-06 02:37:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "014"
down_revision: Union[str, None] = "013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS proposal_calendar_slots (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            proposal_draft_id INTEGER NOT NULL REFERENCES okr_proposal_drafts(id) ON DELETE CASCADE,
            title VARCHAR(255) NOT NULL,
            notes TEXT,
            starts_at TIMESTAMP NOT NULL,
            ends_at TIMESTAMP NOT NULL,
            slot_type VARCHAR(30) NOT NULL DEFAULT 'proposed_block',
            status VARCHAR(20) NOT NULL DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT now(),
            updated_at TIMESTAMP
        )
    """))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_proposal_calendar_slots_user_id "
        "ON proposal_calendar_slots (user_id)"
    ))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_proposal_calendar_slots_proposal_draft_id "
        "ON proposal_calendar_slots (proposal_draft_id)"
    ))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_proposal_calendar_slots_slot_type "
        "ON proposal_calendar_slots (slot_type)"
    ))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_proposal_calendar_slots_status "
        "ON proposal_calendar_slots (status)"
    ))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("DROP TABLE IF EXISTS proposal_calendar_slots"))
