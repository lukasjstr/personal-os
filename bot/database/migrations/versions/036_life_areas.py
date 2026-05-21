"""Add life_areas table + life_area_id on objectives (V3 P10 — Mission Layer).

Revision ID: 036
Revises: 035
Create Date: 2026-05-21
"""
from alembic import op
import sqlalchemy as sa


revision = "036"
down_revision = "035"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "life_areas",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("short_code", sa.String(40), nullable=False),
        sa.Column("vision", sa.Text(), nullable=False, server_default=""),
        sa.Column("current_state", sa.Text(), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("color_hex", sa.String(9), nullable=False, server_default="#888780"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("user_id", "short_code", name="uq_life_areas_user_short"),
    )
    op.create_index("ix_life_areas_user_id", "life_areas", ["user_id"])

    op.add_column(
        "objectives",
        sa.Column(
            "life_area_id",
            sa.Integer(),
            sa.ForeignKey("life_areas.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_objectives_life_area_id", "objectives", ["life_area_id"])


def downgrade() -> None:
    op.drop_index("ix_objectives_life_area_id", table_name="objectives")
    op.drop_column("objectives", "life_area_id")
    op.drop_index("ix_life_areas_user_id", table_name="life_areas")
    op.drop_table("life_areas")
