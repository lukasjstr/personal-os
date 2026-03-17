"""automation_rules table

Revision ID: 024
Revises: 023
Create Date: 2026-03-17
"""
from alembic import op
import sqlalchemy as sa

revision = "024"
down_revision = "023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "automation_rules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("trigger_type", sa.String(60), nullable=False),
        sa.Column("trigger_conditions", sa.JSON(), nullable=True),
        sa.Column("action_type", sa.String(60), nullable=False),
        sa.Column("action_params", sa.JSON(), nullable=True),
        sa.Column("cooldown_hours", sa.Integer(), server_default="24", nullable=False),
        sa.Column("last_triggered_at", sa.DateTime(), nullable=True),
        sa.Column("trigger_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_automation_rules_user_id", "automation_rules", ["user_id"])
    op.create_index("ix_automation_rules_trigger_type", "automation_rules", ["trigger_type"])
    op.create_index("ix_automation_rules_is_active", "automation_rules", ["is_active"])


def downgrade() -> None:
    op.drop_table("automation_rules")
