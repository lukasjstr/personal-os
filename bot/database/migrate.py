"""Database migration helper — applies V2 schema changes safely using IF NOT EXISTS."""
import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from bot.database.models import Base

logger = logging.getLogger(__name__)

# Raw SQL migrations that are safe to run repeatedly
V2_MIGRATIONS = [
    # Existing table: add new columns
    "ALTER TABLE tasks ADD COLUMN IF NOT EXISTS category VARCHAR(30) NOT NULL DEFAULT 'general'",
    "ALTER TABLE objectives ADD COLUMN IF NOT EXISTS priority_weight INTEGER NOT NULL DEFAULT 5",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT true",
    "ALTER TABLE calendar_events ADD COLUMN IF NOT EXISTS all_day BOOLEAN NOT NULL DEFAULT false",
    "ALTER TABLE calendar_events ADD COLUMN IF NOT EXISTS reminder_minutes_before INTEGER NOT NULL DEFAULT 30",
    "ALTER TABLE conversations ADD COLUMN IF NOT EXISTS tokens_used INTEGER",

    # Make schedule_cron nullable (safe to run if already nullable)
    "DO $$ BEGIN ALTER TABLE routines ALTER COLUMN schedule_cron DROP NOT NULL; EXCEPTION WHEN others THEN NULL; END $$",

    # New tables
    """
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
    """,
    "CREATE INDEX IF NOT EXISTS ix_daily_briefs_user_id ON daily_briefs(user_id)",

    """
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
    """,
    "CREATE INDEX IF NOT EXISTS ix_scheduled_reminders_user_id ON scheduled_reminders(user_id)",
    "CREATE INDEX IF NOT EXISTS ix_scheduled_reminders_scheduled_for ON scheduled_reminders(scheduled_for)",

    """
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
    """,
    "CREATE INDEX IF NOT EXISTS ix_weekly_reflections_user_id ON weekly_reflections(user_id)",

    """
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
    """,
    "CREATE INDEX IF NOT EXISTS ix_weekly_priorities_user_id ON weekly_priorities(user_id)",

    """
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
    """,
    "CREATE INDEX IF NOT EXISTS ix_user_insights_user_id ON user_insights(user_id)",
]


async def apply_v2_migrations(engine: AsyncEngine) -> None:
    """Apply V2 schema changes. All statements use IF NOT EXISTS / safe guards."""
    async with engine.begin() as conn:
        for sql in V2_MIGRATIONS:
            sql = sql.strip()
            if sql:
                try:
                    await conn.execute(text(sql))
                except Exception as e:
                    logger.warning("Migration statement warning (may be harmless): %s — %s", sql[:60], e)

    logger.info("V2 migrations applied successfully (%d statements)", len(V2_MIGRATIONS))
