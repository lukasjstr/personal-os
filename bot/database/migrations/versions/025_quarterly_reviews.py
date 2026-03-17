"""quarterly_reviews table

Revision ID: 025
Revises: 024
Create Date: 2026-03-17
"""
from alembic import op
import sqlalchemy as sa

revision = "025"
down_revision = "024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "quarterly_reviews",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("quarter", sa.Integer(), nullable=False),
        sa.Column("quarter_label", sa.String(20), nullable=True),
        sa.Column("life_score", sa.Integer(), nullable=True),
        sa.Column("objectives_data", sa.JSON(), nullable=True),
        sa.Column("ai_analysis", sa.Text(), nullable=True),
        sa.Column("highlights", sa.JSON(), nullable=True),
        sa.Column("challenges", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(20), server_default="completed"),
        sa.Column("generated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "year", "quarter", name="uq_quarterly_review_user_year_quarter"),
    )
    op.create_index("ix_quarterly_reviews_user_id", "quarterly_reviews", ["user_id"])
    op.create_index("ix_quarterly_reviews_year_quarter", "quarterly_reviews", ["year", "quarter"])


def downgrade() -> None:
    op.drop_table("quarterly_reviews")
