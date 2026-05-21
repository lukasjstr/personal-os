"""Add cancelled_reason + cancelled_at to tasks (V3 P09 — Friday-Cut audit trail).

Revision ID: 035
Revises: 034
Create Date: 2026-05-21
"""
from alembic import op
import sqlalchemy as sa


revision = "035"
down_revision = "034"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tasks",
        sa.Column("cancelled_reason", sa.String(60), nullable=True),
    )
    op.add_column(
        "tasks",
        sa.Column("cancelled_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("tasks", "cancelled_at")
    op.drop_column("tasks", "cancelled_reason")
