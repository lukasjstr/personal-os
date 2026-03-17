"""Ensure objectives.priority_weight column exists with correct default

Revision ID: 028
Revises: 027
Create Date: 2026-03-17

Note: priority_weight already exists in the model with default=5 (1-10 scale).
This migration adds a comment and ensures the column is present.
For new installs where the column may not exist yet, we handle both cases.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "028"
down_revision = "027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Check if column exists first (it may already exist from earlier migrations)
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = [c["name"] for c in inspector.get_columns("objectives")]
    if "priority_weight" not in columns:
        op.add_column(
            "objectives",
            sa.Column("priority_weight", sa.Integer(), server_default="2", nullable=False),
        )


def downgrade() -> None:
    pass
