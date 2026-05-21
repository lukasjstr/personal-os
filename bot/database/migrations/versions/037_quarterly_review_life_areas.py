"""Extend quarterly_reviews with life-area scoring (V3 P11).

Adds:
  - life_area_scores      JSONB  {"money": 65, "physical": 78, ...}
  - suggested_next_quarter JSONB
  - user_reflection       Text   (Lukas's own commit)
  - completed_at          DateTime (NULL until /confirm_q)
  - previous_life_score   Integer (for trend display)

Revision ID: 037
Revises: 036
Create Date: 2026-05-21
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision = "037"
down_revision = "036"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "quarterly_reviews",
        sa.Column("life_area_scores", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.add_column(
        "quarterly_reviews",
        sa.Column("suggested_next_quarter", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.add_column(
        "quarterly_reviews",
        sa.Column("user_reflection", sa.Text(), nullable=True),
    )
    op.add_column(
        "quarterly_reviews",
        sa.Column("completed_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "quarterly_reviews",
        sa.Column("previous_life_score", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("quarterly_reviews", "previous_life_score")
    op.drop_column("quarterly_reviews", "completed_at")
    op.drop_column("quarterly_reviews", "user_reflection")
    op.drop_column("quarterly_reviews", "suggested_next_quarter")
    op.drop_column("quarterly_reviews", "life_area_scores")
