"""Structured nutrition logging, life context modes, and personal baseline engine.

Revision ID: 032
Revises: 031
Create Date: 2026-03-22
"""
from alembic import op
import sqlalchemy as sa

revision = "032"
down_revision = "031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── food_entries ─────────────────────────────────────────────────────────
    op.create_table(
        "food_entries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("logged_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("logged_date", sa.Date(), nullable=False),
        sa.Column("meal_type", sa.String(20), nullable=False, server_default="snack"),
        sa.Column("food_name", sa.String(500), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=True),
        sa.Column("unit", sa.String(20), nullable=True),
        sa.Column("calories", sa.Float(), nullable=True),
        sa.Column("protein_g", sa.Float(), nullable=True),
        sa.Column("carbs_g", sa.Float(), nullable=True),
        sa.Column("fat_g", sa.Float(), nullable=True),
        sa.Column("fiber_g", sa.Float(), nullable=True),
        sa.Column("sodium_mg", sa.Float(), nullable=True),
        sa.Column("sugar_g", sa.Float(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("source", sa.String(20), nullable=False, server_default="text"),
        sa.Column("raw_input", sa.Text(), nullable=True),
    )
    op.create_index("ix_food_entries_user_id", "food_entries", ["user_id"])
    op.create_index("ix_food_entries_logged_at", "food_entries", ["logged_at"])
    op.create_index("ix_food_entries_logged_date", "food_entries", ["logged_date"])

    # ── life_contexts ─────────────────────────────────────────────────────────
    op.create_table(
        "life_contexts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("mode", sa.String(20), nullable=False, server_default="normal"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("active_from", sa.Date(), nullable=False),
        sa.Column("active_until", sa.Date(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_life_contexts_user_id", "life_contexts", ["user_id"])
    op.create_index("ix_life_contexts_is_active", "life_contexts", ["is_active"])

    # ── personal_baselines ───────────────────────────────────────────────────
    op.create_table(
        "personal_baselines",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("metric_key", sa.String(50), nullable=False),
        sa.Column("mean_30d", sa.Float(), nullable=True),
        sa.Column("std_30d", sa.Float(), nullable=True),
        sa.Column("mean_90d", sa.Float(), nullable=True),
        sa.Column("min_ever", sa.Float(), nullable=True),
        sa.Column("max_ever", sa.Float(), nullable=True),
        sa.Column("days_tracked", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_updated", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_personal_baselines_user_id", "personal_baselines", ["user_id"])
    op.create_unique_constraint(
        "uq_baseline_user_metric", "personal_baselines", ["user_id", "metric_key"]
    )


def downgrade() -> None:
    op.drop_table("personal_baselines")
    op.drop_table("life_contexts")
    op.drop_table("food_entries")
