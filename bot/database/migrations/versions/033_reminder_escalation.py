"""Add severity + escalation_step + linked_objective_id to scheduled_reminders (P07).

Revision ID: 033
Revises: 032
Create Date: 2026-05-21
"""
from alembic import op
import sqlalchemy as sa


revision = "033"
down_revision = "032"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "scheduled_reminders",
        sa.Column("severity", sa.String(20), nullable=False, server_default="normal"),
    )
    op.add_column(
        "scheduled_reminders",
        sa.Column("escalation_step", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "scheduled_reminders",
        sa.Column(
            "linked_objective_id",
            sa.Integer(),
            sa.ForeignKey("objectives.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_scheduled_reminders_severity_step",
        "scheduled_reminders",
        ["severity", "escalation_step"],
    )


def downgrade() -> None:
    op.drop_index("ix_scheduled_reminders_severity_step", table_name="scheduled_reminders")
    op.drop_column("scheduled_reminders", "linked_objective_id")
    op.drop_column("scheduled_reminders", "escalation_step")
    op.drop_column("scheduled_reminders", "severity")
