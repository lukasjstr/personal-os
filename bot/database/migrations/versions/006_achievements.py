"""Phase 7.1 — Achievement & Milestone System

Revision ID: 006
Revises: 005
Create Date: 2026-03-02 00:00:00.000000

Adds:
- achievements table: id, key, title, description, emoji, category, xp_reward,
  condition_type, condition_value
- user_achievements table: id, user_id, achievement_id, unlocked_at
- Seed data: 14 achievements
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # Create achievements table
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS achievements (
            id SERIAL PRIMARY KEY,
            key TEXT UNIQUE NOT NULL,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            emoji TEXT NOT NULL,
            category TEXT NOT NULL,
            xp_reward INTEGER DEFAULT 0,
            condition_type TEXT NOT NULL,
            condition_value INTEGER NOT NULL
        )
    """))

    # Create user_achievements table
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS user_achievements (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            achievement_id INTEGER REFERENCES achievements(id),
            unlocked_at TIMESTAMP DEFAULT now(),
            UNIQUE(user_id, achievement_id)
        )
    """))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_user_achievements_user_id ON user_achievements(user_id)"
    ))

    # Seed achievements
    achievements = [
        (
            "erster_schritt",
            "Erster Schritt",
            "Onboarding abgeschlossen",
            "🎓",
            "onboarding",
            50,
            "milestone",
            1,
        ),
        (
            "macher",
            "Macher",
            "10 Tasks erledigt",
            "✅",
            "tasks",
            100,
            "count",
            10,
        ),
        (
            "hundertschaft",
            "Hundertschaft",
            "100 Tasks erledigt",
            "💯",
            "tasks",
            500,
            "count",
            100,
        ),
        (
            "zielstrebig",
            "Zielstrebig",
            "Erstes Objective erstellt",
            "🎯",
            "goals",
            75,
            "count",
            1,
        ),
        (
            "kr_knacker",
            "Key Result Knacker",
            "Erstes Key Result zu 100% abgeschlossen",
            "🏅",
            "goals",
            200,
            "milestone",
            1,
        ),
        (
            "feuer_gefangen",
            "Feuer gefangen",
            "7-Tage-Streak erreicht",
            "🔥",
            "streaks",
            150,
            "streak",
            7,
        ),
        (
            "diamant_disziplin",
            "Diamant-Disziplin",
            "30-Tage-Streak erreicht",
            "💎",
            "streaks",
            500,
            "streak",
            30,
        ),
        (
            "legende",
            "Legende",
            "100-Tage-Streak erreicht",
            "🌟",
            "streaks",
            2000,
            "streak",
            100,
        ),
        (
            "selbstreflektiert",
            "Selbstreflektiert",
            "Erste Weekly Reflection abgeschlossen",
            "🪞",
            "reflection",
            100,
            "count",
            1,
        ),
        (
            "hydration_hero",
            "Hydration Hero",
            "Insgesamt 100 Liter Wasser getrunken",
            "💧",
            "fun",
            300,
            "count",
            100,
        ),
        (
            "perfekte_woche",
            "Perfekte Woche",
            "Eine Woche mit 100% Completion abgeschlossen",
            "🎯",
            "fun",
            250,
            "milestone",
            1,
        ),
        (
            "comeback_kid",
            "Comeback Kid",
            "Nach 7 Tagen Pause wieder aktiv geworden",
            "🔄",
            "fun",
            150,
            "milestone",
            1,
        ),
        (
            "brain_dumper",
            "Brain Dumper",
            "50 Brain Dumps erfasst",
            "🧠",
            "tasks",
            200,
            "count",
            50,
        ),
        (
            "gym_rat",
            "Gym Rat",
            "100 Workouts absolviert",
            "💪",
            "tasks",
            400,
            "count",
            100,
        ),
    ]

    for (key, title, description, emoji, category, xp_reward, condition_type, condition_value) in achievements:
        conn.execute(sa.text("""
            INSERT INTO achievements (key, title, description, emoji, category, xp_reward, condition_type, condition_value)
            VALUES (:key, :title, :description, :emoji, :category, :xp_reward, :condition_type, :condition_value)
            ON CONFLICT (key) DO NOTHING
        """), {
            "key": key,
            "title": title,
            "description": description,
            "emoji": emoji,
            "category": category,
            "xp_reward": xp_reward,
            "condition_type": condition_type,
            "condition_value": condition_value,
        })


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("DROP INDEX IF EXISTS ix_user_achievements_user_id"))
    conn.execute(sa.text("DROP TABLE IF EXISTS user_achievements"))
    conn.execute(sa.text("DROP TABLE IF EXISTS achievements"))
