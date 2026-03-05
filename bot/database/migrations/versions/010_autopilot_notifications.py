"""Phase A1 — Add autopilot_notifications table

Revision ID: 010
Revises: 009
Create Date: 2026-03-05 00:00:00.000000

Adds:
- autopilot_notifications table: stores pending nudges/reminders for mobile + Telegram surfaces
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
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS autopilot_notifications (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            notification_type VARCHAR(50) NOT NULL DEFAULT 'generic',
            title VARCHAR(500) NOT NULL,
            body TEXT,
            status VARCHAR(20) NOT NULL DEFAULT 'pending',
            snoozed_until TIMESTAMP,
            source VARCHAR(30) NOT NULL DEFAULT 'autopilot',
            linked_task_id INTEGER REFERENCES tasks(id) ON DELETE SET NULL,
            created_at TIMESTAMP DEFAULT now(),
            updated_at TIMESTAMP
        )
    """))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_autopilot_notifications_user_id "
        "ON autopilot_notifications (user_id)"
    ))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_autopilot_notifications_status "
        "ON autopilot_notifications (status)"
    ))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("DROP TABLE IF EXISTS autopilot_notifications"))
