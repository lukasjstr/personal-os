"""daily_context and evening_checkin tables

Revision ID: 022
Revises: 021
Create Date: 2026-03-17
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "022"
down_revision = "021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "daily_contexts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("energy", sa.Integer(), nullable=True),
        sa.Column("hours_available", sa.Float(), nullable=True),
        sa.Column("focus_area", sa.String(100), nullable=True),
        sa.Column("mood_note", sa.Text(), nullable=True),
        sa.Column("daily_plan", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "date", name="uq_daily_context_user_date"),
    )
    op.create_index("ix_daily_contexts_user_id", "daily_contexts", ["user_id"])
    op.create_index("ix_daily_contexts_date", "daily_contexts", ["date"])

    op.create_table(
        "evening_checkins",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("tasks_planned", sa.Integer(), default=0),
        sa.Column("tasks_completed", sa.Integer(), default=0),
        sa.Column("completed_task_ids", JSONB, nullable=True),
        sa.Column("win_of_day", sa.Text(), nullable=True),
        sa.Column("blocker", sa.Text(), nullable=True),
        sa.Column("gap_analysis", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "date", name="uq_evening_checkin_user_date"),
    )
    op.create_index("ix_evening_checkins_user_id", "evening_checkins", ["user_id"])
    op.create_index("ix_evening_checkins_date", "evening_checkins", ["date"])


def downgrade() -> None:
    op.drop_table("evening_checkins")
    op.drop_table("daily_contexts")
