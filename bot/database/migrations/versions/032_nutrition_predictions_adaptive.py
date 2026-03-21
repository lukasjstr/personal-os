"""Nutrition Intelligence + Predictions + Adaptive Goals

Tables added:
- nutrition_entries: Per-meal nutrient breakdown (macros + micros)
- nutrient_targets: Daily nutrient targets per user
- predictions: Stored predictive analytics results
- goal_adjustments: Auto-suggested target adjustments
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "032"
down_revision = "031_push_subscriptions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ─── Nutrition Entries ─────────────────────────────────────────────────
    op.create_table(
        "nutrition_entries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("log_id", sa.Integer(), sa.ForeignKey("logs.id", ondelete="SET NULL"), index=True),
        sa.Column("date", sa.Date(), nullable=False, index=True),
        sa.Column("food_description", sa.Text(), nullable=False),
        sa.Column("meal_type", sa.String(20)),
        sa.Column("calories", sa.Float()),
        sa.Column("protein_g", sa.Float()),
        sa.Column("carbs_g", sa.Float()),
        sa.Column("fat_g", sa.Float()),
        sa.Column("fiber_g", sa.Float()),
        sa.Column("sugar_g", sa.Float()),
        sa.Column("sodium_mg", sa.Float()),
        sa.Column("potassium_mg", sa.Float()),
        sa.Column("caffeine_mg", sa.Float()),
        sa.Column("water_ml", sa.Float()),
        sa.Column("additional_nutrients", JSONB(), server_default="{}"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # ─── Nutrient Targets ─────────────────────────────────────────────────
    op.create_table(
        "nutrient_targets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("nutrient", sa.String(50), nullable=False),
        sa.Column("target_min", sa.Float()),
        sa.Column("target_max", sa.Float()),
        sa.Column("unit", sa.String(20), nullable=False, server_default="g"),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "nutrient", name="uq_nutrient_target_user_nutrient"),
    )

    # ─── Predictions ──────────────────────────────────────────────────────
    op.create_table(
        "predictions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("prediction_type", sa.String(50), nullable=False, index=True),
        sa.Column("entity_type", sa.String(50)),
        sa.Column("entity_id", sa.Integer()),
        sa.Column("predicted_value", sa.Float()),
        sa.Column("predicted_date", sa.Date()),
        sa.Column("confidence", sa.Float(), server_default="0.0"),
        sa.Column("explanation", sa.Text()),
        sa.Column("data", JSONB()),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # ─── Goal Adjustments ─────────────────────────────────────────────────
    op.create_table(
        "goal_adjustments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("entity_type", sa.String(30), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("adjustment_type", sa.String(30), nullable=False),
        sa.Column("old_value", sa.Text()),
        sa.Column("new_value", sa.Text()),
        sa.Column("reason", sa.Text()),
        sa.Column("status", sa.String(20), nullable=False, server_default="suggested", index=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("resolved_at", sa.DateTime()),
    )


def downgrade() -> None:
    op.drop_table("goal_adjustments")
    op.drop_table("predictions")
    op.drop_table("nutrient_targets")
    op.drop_table("nutrition_entries")
