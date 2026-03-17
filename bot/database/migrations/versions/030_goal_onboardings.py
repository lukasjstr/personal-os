"""Goal onboardings table for conversational coaching flow.

Revision ID: 030
Revises: 029
Create Date: 2026-03-17
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "030"
down_revision = "029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "goal_onboardings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="in_progress"),
        sa.Column("current_step", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("goal_input", sa.Text(), nullable=False),
        sa.Column("raw_answers", sa.JSON(), server_default="{}"),
        sa.Column("draft_payload", JSONB(), nullable=True),
        sa.Column("proposal_draft_id", sa.Integer(), sa.ForeignKey("okr_proposal_drafts.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_goal_onboardings_user_id", "goal_onboardings", ["user_id"])
    op.create_index("ix_goal_onboardings_status", "goal_onboardings", ["status"])


def downgrade() -> None:
    op.drop_table("goal_onboardings")
