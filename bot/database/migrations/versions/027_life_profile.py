"""life_profiles table — persistent compressed life memory

Revision ID: 027
Revises: 026
Create Date: 2026-03-17
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON

revision = "027"
down_revision = "026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "life_profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("strengths", JSON(), nullable=True),
        sa.Column("patterns", JSON(), nullable=True),
        sa.Column("current_focus", sa.String(500), nullable=True),
        sa.Column("last_updated", sa.DateTime(), nullable=True),
        sa.Column("update_count", sa.Integer(), server_default="0"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", name="uq_life_profile_user_id"),
    )
    op.create_index("ix_life_profiles_user_id", "life_profiles", ["user_id"])


def downgrade() -> None:
    op.drop_table("life_profiles")
