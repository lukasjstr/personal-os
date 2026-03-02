"""Phase 7.2 — Add xp and level to users table

Revision ID: 007
Revises: 006
Create Date: 2026-03-02 00:00:00.000000

Adds:
- users.xp INTEGER DEFAULT 0
- users.level INTEGER DEFAULT 1
- Backfills initial XP from existing activity (tasks, routines, brain_dumps, logs, achievements)
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    conn.execute(sa.text(
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS xp INTEGER NOT NULL DEFAULT 0"
    ))
    conn.execute(sa.text(
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS level INTEGER NOT NULL DEFAULT 1"
    ))

    # Backfill XP from existing activity using new reward values:
    #   task done: +10, routine completion: +5, brain dump: +15, log: +5, achievement xp_reward
    conn.execute(sa.text("""
        UPDATE users u SET xp = (
            COALESCE((
                SELECT COUNT(*) * 10
                FROM tasks
                WHERE user_id = u.id AND status = 'done'
            ), 0)
            + COALESCE((
                SELECT COUNT(*) * 5
                FROM routine_completions
                WHERE user_id = u.id
            ), 0)
            + COALESCE((
                SELECT COUNT(*) * 15
                FROM brain_dumps
                WHERE user_id = u.id
            ), 0)
            + COALESCE((
                SELECT COUNT(*) * 5
                FROM logs
                WHERE user_id = u.id
            ), 0)
            + COALESCE((
                SELECT SUM(a.xp_reward)
                FROM user_achievements ua
                JOIN achievements a ON ua.achievement_id = a.id
                WHERE ua.user_id = u.id
            ), 0)
        )
    """))

    # Compute level from backfilled XP: level = floor(sqrt(xp / 100)), minimum 1
    conn.execute(sa.text("""
        UPDATE users
        SET level = GREATEST(1, FLOOR(SQRT(xp::float / 100))::integer)
    """))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("ALTER TABLE users DROP COLUMN IF EXISTS level"))
    conn.execute(sa.text("ALTER TABLE users DROP COLUMN IF EXISTS xp"))
