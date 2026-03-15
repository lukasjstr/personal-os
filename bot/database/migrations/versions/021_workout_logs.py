"""Add workout_logs table for structured weight tracking

Revision ID: 021
Revises: 020
Create Date: 2026-03-15
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "021"
down_revision: Union[str, None] = "020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "workout_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("exercise", sa.String(200), nullable=False),
        sa.Column("weight_kg", sa.Float(), nullable=True),
        sa.Column("sets", sa.Integer(), nullable=True),
        sa.Column("reps", sa.Integer(), nullable=True),
        sa.Column("logged_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_workout_logs_user_id", "workout_logs", ["user_id"])
    op.create_index("ix_workout_logs_exercise", "workout_logs", ["exercise"])
    op.create_index("ix_workout_logs_logged_date", "workout_logs", ["logged_date"])


def downgrade() -> None:
    op.drop_index("ix_workout_logs_logged_date", "workout_logs")
    op.drop_index("ix_workout_logs_exercise", "workout_logs")
    op.drop_index("ix_workout_logs_user_id", "workout_logs")
    op.drop_table("workout_logs")
