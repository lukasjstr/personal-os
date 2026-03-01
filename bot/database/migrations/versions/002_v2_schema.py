"""V2 schema — add new columns and 5 new tables

Revision ID: 002
Revises: 001
Create Date: 2026-03-01 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON
from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # ── tasks: add category column ─────────────────────────────────────────────
    conn.execute(sa.text(
        "ALTER TABLE tasks ADD COLUMN IF NOT EXISTS category VARCHAR(30) NOT NULL DEFAULT 'general'"
    ))

    # ── objectives: add priority_weight ───────────────────────────────────────
    conn.execute(sa.text(
        "ALTER TABLE objectives ADD COLUMN IF NOT EXISTS priority_weight INTEGER NOT NULL DEFAULT 5"
    ))

    # ── users: add is_active ──────────────────────────────────────────────────
    conn.execute(sa.text(
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT true"
    ))

    # ── routines: make schedule_cron nullable ─────────────────────────────────
    conn.execute(sa.text(
        "ALTER TABLE routines ALTER COLUMN schedule_cron DROP NOT NULL"
    ))

    # ── calendar_events: add all_day, reminder_minutes_before ─────────────────
    conn.execute(sa.text(
        "ALTER TABLE calendar_events ADD COLUMN IF NOT EXISTS all_day BOOLEAN NOT NULL DEFAULT false"
    ))
    conn.execute(sa.text(
        "ALTER TABLE calendar_events ADD COLUMN IF NOT EXISTS reminder_minutes_before INTEGER NOT NULL DEFAULT 30"
    ))

    # ── conversations: add tokens_used ────────────────────────────────────────
    conn.execute(sa.text(
        "ALTER TABLE conversations ADD COLUMN IF NOT EXISTS tokens_used INTEGER"
    ))

    # ── daily_briefs ──────────────────────────────────────────────────────────
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS daily_briefs (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            brief_date DATE NOT NULL,
            priorities JSON NOT NULL DEFAULT '[]',
            routines_snapshot JSON NOT NULL DEFAULT '[]',
            calendar_snapshot JSON NOT NULL DEFAULT '[]',
            warnings JSON NOT NULL DEFAULT '[]',
            user_adjusted BOOLEAN NOT NULL DEFAULT false,
            adjusted_priorities JSON,
            brief_sent_at TIMESTAMP,
            review_sent_at TIMESTAMP,
            day_score INTEGER,
            day_notes TEXT,
            created_at TIMESTAMP NOT NULL DEFAULT now(),
            UNIQUE(user_id, brief_date)
        )
    """))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_daily_briefs_user_id ON daily_briefs(user_id)"))

    # ── scheduled_reminders ───────────────────────────────────────────────────
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS scheduled_reminders (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            reminder_type VARCHAR(30) NOT NULL,
            message TEXT NOT NULL,
            scheduled_for TIMESTAMP NOT NULL,
            repeat_rule VARCHAR(100),
            linked_key_result_id INTEGER REFERENCES key_results(id) ON DELETE SET NULL,
            linked_task_id INTEGER REFERENCES tasks(id) ON DELETE SET NULL,
            linked_routine_id INTEGER REFERENCES routines(id) ON DELETE SET NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'pending',
            sent_at TIMESTAMP,
            auto_generated BOOLEAN NOT NULL DEFAULT true,
            created_at TIMESTAMP NOT NULL DEFAULT now()
        )
    """))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_scheduled_reminders_user_id ON scheduled_reminders(user_id)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_scheduled_reminders_scheduled_for ON scheduled_reminders(scheduled_for)"))

    # ── weekly_reflections ────────────────────────────────────────────────────
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS weekly_reflections (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            week_start DATE NOT NULL,
            week_number INTEGER NOT NULL,
            year INTEGER NOT NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'pending',
            current_question INTEGER NOT NULL DEFAULT 0,
            stats_snapshot JSON NOT NULL DEFAULT '{}',
            biggest_win TEXT,
            biggest_blocker TEXT,
            key_learning TEXT,
            raw_answers JSON NOT NULL DEFAULT '{}',
            priorities_next_week JSON,
            created_at TIMESTAMP NOT NULL DEFAULT now(),
            updated_at TIMESTAMP,
            UNIQUE(user_id, week_start)
        )
    """))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_weekly_reflections_user_id ON weekly_reflections(user_id)"))

    # ── weekly_priorities ─────────────────────────────────────────────────────
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS weekly_priorities (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            week_start DATE NOT NULL,
            priority_rank INTEGER NOT NULL,
            title VARCHAR(500) NOT NULL,
            linked_objective_id INTEGER REFERENCES objectives(id) ON DELETE SET NULL,
            linked_key_result_id INTEGER REFERENCES key_results(id) ON DELETE SET NULL,
            linked_task_id INTEGER REFERENCES tasks(id) ON DELETE SET NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'active',
            created_at TIMESTAMP NOT NULL DEFAULT now(),
            updated_at TIMESTAMP
        )
    """))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_weekly_priorities_user_id ON weekly_priorities(user_id)"))

    # ── user_insights ─────────────────────────────────────────────────────────
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS user_insights (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            insight_type VARCHAR(50) NOT NULL,
            title VARCHAR(500) NOT NULL,
            description TEXT NOT NULL,
            data_basis JSON,
            active BOOLEAN NOT NULL DEFAULT true,
            source VARCHAR(30) NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT now(),
            updated_at TIMESTAMP
        )
    """))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_user_insights_user_id ON user_insights(user_id)"))


def downgrade() -> None:
    op.drop_table("user_insights")
    op.drop_table("weekly_priorities")
    op.drop_table("weekly_reflections")
    op.drop_table("scheduled_reminders")
    op.drop_table("daily_briefs")

    conn = op.get_bind()
    conn.execute(sa.text("ALTER TABLE conversations DROP COLUMN IF EXISTS tokens_used"))
    conn.execute(sa.text("ALTER TABLE calendar_events DROP COLUMN IF EXISTS reminder_minutes_before"))
    conn.execute(sa.text("ALTER TABLE calendar_events DROP COLUMN IF EXISTS all_day"))
    conn.execute(sa.text("ALTER TABLE routines ALTER COLUMN schedule_cron SET NOT NULL"))
    conn.execute(sa.text("ALTER TABLE users DROP COLUMN IF EXISTS is_active"))
    conn.execute(sa.text("ALTER TABLE objectives DROP COLUMN IF EXISTS priority_weight"))
    conn.execute(sa.text("ALTER TABLE tasks DROP COLUMN IF EXISTS category"))
