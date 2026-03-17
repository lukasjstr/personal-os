"""learning_items and learning_reviews tables

Revision ID: 029
Revises: 028
Create Date: 2026-03-17
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON

revision = "029"
down_revision = "028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "learning_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("item_type", sa.String(60), nullable=False, server_default="note"),
        sa.Column("source", sa.String(300), nullable=True),
        sa.Column("skill_level", sa.Integer(), server_default="1"),
        sa.Column("next_review_at", sa.DateTime(), nullable=True),
        sa.Column("review_count", sa.Integer(), server_default="0"),
        sa.Column("last_reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("ease_factor", sa.Float(), server_default="2.5"),
        sa.Column("ai_summary", sa.Text(), nullable=True),
        sa.Column("tags", JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), onupdate=sa.func.now()),
    )
    op.create_index("ix_learning_items_user_id", "learning_items", ["user_id"])
    op.create_index("ix_learning_items_next_review", "learning_items", ["next_review_at"])
    op.create_index("ix_learning_items_item_type", "learning_items", ["item_type"])

    op.create_table(
        "learning_reviews",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("item_id", sa.Integer(), sa.ForeignKey("learning_items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("quality", sa.Integer(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("notes", sa.Text(), nullable=True),
    )
    op.create_index("ix_learning_reviews_user_id", "learning_reviews", ["user_id"])
    op.create_index("ix_learning_reviews_item_id", "learning_reviews", ["item_id"])


def downgrade() -> None:
    op.drop_table("learning_reviews")
    op.drop_table("learning_items")
