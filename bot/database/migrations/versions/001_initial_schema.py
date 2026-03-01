"""Initial schema

Revision ID: 001
Revises:
Create Date: 2026-03-01 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON
from alembic import op

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("telegram_id", sa.BigInteger(), unique=True, nullable=False),
        sa.Column("telegram_username", sa.String(255), nullable=True),
        sa.Column("first_name", sa.String(255), nullable=True),
        sa.Column("timezone", sa.String(64), server_default="Europe/Berlin"),
        sa.Column("settings", JSON, server_default="{}"),
        sa.Column("morning_brief_time", sa.String(5), server_default="06:30"),
        sa.Column("evening_review_time", sa.String(5), server_default="21:00"),
        sa.Column("api_token", sa.String(64), unique=True, nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_users_telegram_id", "users", ["telegram_id"])
    op.create_index("ix_users_api_token", "users", ["api_token"])

    op.create_table(
        "objectives",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(50), server_default="personal"),
        sa.Column("status", sa.String(20), server_default="active"),
        sa.Column("target_date", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_objectives_user_id", "objectives", ["user_id"])

    op.create_table(
        "key_results",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("objective_id", sa.Integer(), sa.ForeignKey("objectives.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("metric_type", sa.String(20), server_default="number"),
        sa.Column("target_value", sa.Float(), nullable=True),
        sa.Column("current_value", sa.Float(), server_default="0"),
        sa.Column("unit", sa.String(50), nullable=True),
        sa.Column("frequency", sa.String(20), server_default="weekly"),
        sa.Column("status", sa.String(20), server_default="active"),
        sa.Column("target_date", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_key_results_objective_id", "key_results", ["objective_id"])
    op.create_index("ix_key_results_user_id", "key_results", ["user_id"])

    op.create_table(
        "tasks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key_result_id", sa.Integer(), sa.ForeignKey("key_results.id", ondelete="SET NULL"), nullable=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), server_default="todo"),
        sa.Column("priority", sa.Integer(), server_default="3"),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_tasks_user_id", "tasks", ["user_id"])
    op.create_index("ix_tasks_key_result_id", "tasks", ["key_result_id"])

    op.create_table(
        "logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("key_result_id", sa.Integer(), sa.ForeignKey("key_results.id", ondelete="SET NULL"), nullable=True),
        sa.Column("task_id", sa.Integer(), sa.ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True),
        sa.Column("log_type", sa.String(30), nullable=False),
        sa.Column("data", JSON, nullable=False),
        sa.Column("source", sa.String(20), server_default="text"),
        sa.Column("raw_input", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("logged_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_logs_user_id", "logs", ["user_id"])
    op.create_index("ix_logs_log_type", "logs", ["log_type"])
    op.create_index("ix_logs_created_at", "logs", ["created_at"])

    op.create_table(
        "routines",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("schedule_cron", sa.String(100), nullable=False),
        sa.Column("frequency_human", sa.String(100), nullable=True),
        sa.Column("linked_key_result_id", sa.Integer(), sa.ForeignKey("key_results.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.String(20), server_default="active"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_routines_user_id", "routines", ["user_id"])

    op.create_table(
        "routine_completions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("routine_id", sa.Integer(), sa.ForeignKey("routines.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("logged_via", sa.String(20), server_default="telegram"),
        sa.Column("notes", sa.Text(), nullable=True),
    )
    op.create_index("ix_routine_completions_routine_id", "routine_completions", ["routine_id"])
    op.create_index("ix_routine_completions_user_id", "routine_completions", ["user_id"])

    op.create_table(
        "calendar_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("start_time", sa.DateTime(), nullable=False),
        sa.Column("end_time", sa.DateTime(), nullable=True),
        sa.Column("event_type", sa.String(30), server_default="reminder"),
        sa.Column("linked_task_id", sa.Integer(), sa.ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True),
        sa.Column("linked_routine_id", sa.Integer(), sa.ForeignKey("routines.id", ondelete="SET NULL"), nullable=True),
        sa.Column("ical_uid", sa.String(255), unique=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_calendar_events_user_id", "calendar_events", ["user_id"])
    op.create_index("ix_calendar_events_start_time", "calendar_events", ["start_time"])

    op.create_table(
        "brain_dumps",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("raw_input", sa.Text(), nullable=False),
        sa.Column("processed", sa.Boolean(), server_default="false"),
        sa.Column("ai_interpretation", sa.Text(), nullable=True),
        sa.Column("linked_objective_id", sa.Integer(), sa.ForeignKey("objectives.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_brain_dumps_user_id", "brain_dumps", ["user_id"])

    op.create_table(
        "conversations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("metadata", JSON, nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("session_date", sa.Date(), nullable=False),
    )
    op.create_index("ix_conversations_user_id", "conversations", ["user_id"])
    op.create_index("ix_conversations_session_date", "conversations", ["session_date"])
    op.create_index("ix_conversations_created_at", "conversations", ["created_at"])


def downgrade() -> None:
    op.drop_table("conversations")
    op.drop_table("brain_dumps")
    op.drop_table("calendar_events")
    op.drop_table("routine_completions")
    op.drop_table("routines")
    op.drop_table("logs")
    op.drop_table("tasks")
    op.drop_table("key_results")
    op.drop_table("objectives")
    op.drop_table("users")
