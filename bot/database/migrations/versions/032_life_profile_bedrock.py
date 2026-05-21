"""Add bedrock layer to life_profiles (P02 — Lukas-Kalibrierung)

Revision ID: 032
Revises: 031
Create Date: 2026-05-21

Adds 3 columns to life_profiles:
- bedrock         JSONB — hand-curated identity (life areas, levers, leitspruch, …)
- bedrock_updated_at  DateTime — last time bedrock was modified
- bedrock_history JSONB — versioned snapshots for rollback
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision = "032"
down_revision = "031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "life_profiles",
        sa.Column("bedrock", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.add_column(
        "life_profiles",
        sa.Column("bedrock_updated_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "life_profiles",
        sa.Column("bedrock_history", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
    )


def downgrade() -> None:
    op.drop_column("life_profiles", "bedrock_history")
    op.drop_column("life_profiles", "bedrock_updated_at")
    op.drop_column("life_profiles", "bedrock")
