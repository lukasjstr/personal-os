"""financial_transactions and budgets tables

Revision ID: 023
Revises: 022
Create Date: 2026-03-17
"""
from alembic import op
import sqlalchemy as sa

revision = "023"
down_revision = "022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "financial_transactions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("type", sa.String(10), nullable=False),  # income | expense
        sa.Column("category", sa.String(60), nullable=False, server_default="sonstiges"),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("transaction_date", sa.Date(), nullable=False),
        sa.Column("is_recurring", sa.Boolean(), server_default="false"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_fin_tx_user_id", "financial_transactions", ["user_id"])
    op.create_index("ix_fin_tx_date", "financial_transactions", ["transaction_date"])
    op.create_index("ix_fin_tx_type", "financial_transactions", ["type"])

    op.create_table(
        "budgets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("category", sa.String(60), nullable=False),
        sa.Column("monthly_limit", sa.Numeric(10, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), onupdate=sa.func.now()),
        sa.UniqueConstraint("user_id", "category", name="uq_budget_user_category"),
    )
    op.create_index("ix_budgets_user_id", "budgets", ["user_id"])


def downgrade() -> None:
    op.drop_table("budgets")
    op.drop_table("financial_transactions")
