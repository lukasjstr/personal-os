"""Add paused_at + paused_reason to objectives (V3 P08 — /cut audit trail).

Revision ID: 034
Revises: 033
Create Date: 2026-05-21
"""
from alembic import op
import sqlalchemy as sa


revision = "034"
down_revision = "033"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "objectives",
        sa.Column("paused_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "objectives",
        sa.Column("paused_reason", sa.String(60), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("objectives", "paused_reason")
    op.drop_column("objectives", "paused_at")
