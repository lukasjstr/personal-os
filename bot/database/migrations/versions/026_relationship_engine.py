"""contacts, interactions, commitments tables

Revision ID: 026
Revises: 025
Create Date: 2026-03-17
"""
from alembic import op
import sqlalchemy as sa

revision = "026"
down_revision = "025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "contacts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("nickname", sa.String(100), nullable=True),
        sa.Column("relationship_type", sa.String(60), server_default="friend", nullable=False),
        sa.Column("contact_frequency_days", sa.Integer(), server_default="30", nullable=False),
        sa.Column("last_contacted_at", sa.DateTime(), nullable=True),
        sa.Column("birthday", sa.Date(), nullable=True),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("email", sa.String(200), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_contacts_user_id", "contacts", ["user_id"])
    op.create_index("ix_contacts_relationship_type", "contacts", ["relationship_type"])

    op.create_table(
        "interactions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("contact_id", sa.Integer(), sa.ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("interaction_type", sa.String(60), nullable=False),
        sa.Column("quality_score", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("interacted_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_interactions_user_id", "interactions", ["user_id"])
    op.create_index("ix_interactions_contact_id", "interactions", ["contact_id"])

    op.create_table(
        "commitments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("contact_id", sa.Integer(), sa.ForeignKey("contacts.id", ondelete="CASCADE"), nullable=True),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(20), server_default="pending", nullable=False),
        sa.Column("reminder_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_commitments_user_id", "commitments", ["user_id"])
    op.create_index("ix_commitments_status", "commitments", ["status"])
    op.create_index("ix_commitments_contact_id", "commitments", ["contact_id"])


def downgrade() -> None:
    op.drop_table("commitments")
    op.drop_table("interactions")
    op.drop_table("contacts")
