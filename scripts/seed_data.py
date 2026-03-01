"""Seed test data for Personal OS V2 development."""
import asyncio
import os
import secrets
import sys
import uuid
from datetime import date, datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot.database.connection import AsyncSessionLocal, engine
from bot.database.models import (
    Base, BrainDump, CalendarEvent, KeyResult, Log,
    Objective, Routine, Task, User,
)


async def seed() -> None:
    # Create all tables first
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        # ─── User ─────────────────────────────────────────────────────────────
        telegram_id = int(os.environ.get("SEED_TELEGRAM_ID", "123456789"))
        user = User(
            telegram_id=telegram_id,
            telegram_username="testuser",
            first_name="Test",
            timezone="Europe/Berlin",
            is_active=True,
            settings={
                "priorities_enabled": True,
                "review_enabled": True,
                "proactive_enabled": True,
                "reflection_enabled": True,
                "morning_brief_time": "06:30",
                "evening_review_time": "21:00",
                "weekly_reflection_day": "sunday",
                "weekly_reflection_time": "19:00",
                "shopping_reminder_day": "saturday",
                "shopping_reminder_time": "10:00",
                "ical_token": str(uuid.uuid4()),
            },
            api_token=secrets.token_urlsafe(32),
        )
        session.add(user)
        await session.flush()
        print(f"✅ User #{user.id} erstellt (telegram_id={telegram_id})")
        print(f"   API Token: {user.api_token}")
        print(f"   iCal Token: {user.settings['ical_token']}")

        # ─── Objective 1: Gesünder leben ──────────────────────────────────────
        obj_health = Objective(
            user_id=user.id,
            title="Gesünder leben",
            category="health",
            description="Gesündere Gewohnheiten aufbauen",
            status="active",
            priority_weight=8,
        )
        session.add(obj_health)
        await session.flush()

        kr_water = KeyResult(
            objective_id=obj_health.id,
            user_id=user.id,
            title="3L Wasser täglich",
            metric_type="number",
            target_value=3.0,
            current_value=0.0,
            unit="Liter",
            frequency="daily",
            status="active",
        )
        kr_training = KeyResult(
            objective_id=obj_health.id,
            user_id=user.id,
            title="4x Training pro Woche",
            metric_type="number",
            target_value=4,
            current_value=1.0,
            unit="Einheiten",
            frequency="weekly",
            status="active",
        )
        session.add(kr_water)
        session.add(kr_training)
        await session.flush()
        print(f"✅ Objective: Gesünder leben (#{obj_health.id})")

        # ─── Objective 2: Business aufbauen ───────────────────────────────────
        obj_biz = Objective(
            user_id=user.id,
            title="Business aufbauen",
            category="business",
            description="Landingpage live, LinkedIn Content",
            status="active",
            priority_weight=9,
            target_date=date.today() + timedelta(days=30),
        )
        session.add(obj_biz)
        await session.flush()

        kr_landing = KeyResult(
            objective_id=obj_biz.id,
            user_id=user.id,
            title="Landingpage live",
            metric_type="checklist",
            target_value=None,
            current_value=0.0,
            frequency="once",
            status="active",
        )
        kr_linkedin = KeyResult(
            objective_id=obj_biz.id,
            user_id=user.id,
            title="10 LinkedIn Posts pro Monat",
            metric_type="number",
            target_value=10,
            current_value=2.0,
            unit="Posts",
            frequency="monthly",
            status="active",
        )
        session.add(kr_landing)
        session.add(kr_linkedin)
        await session.flush()
        print(f"✅ Objective: Business aufbauen (#{obj_biz.id})")

        # ─── Tasks ────────────────────────────────────────────────────────────
        task1 = Task(
            user_id=user.id,
            key_result_id=kr_landing.id,
            title="Hero Section schreiben",
            category="work",
            priority=2,
            status="todo",
        )
        task2 = Task(
            user_id=user.id,
            key_result_id=kr_landing.id,
            title="Testimonials sammeln",
            category="work",
            priority=2,
            status="todo",
        )
        task3 = Task(
            user_id=user.id,
            key_result_id=kr_landing.id,
            title="CTA testen",
            category="work",
            priority=3,
            status="todo",
        )
        session.add(task1)
        session.add(task2)
        session.add(task3)

        # ─── Shopping Items ───────────────────────────────────────────────────
        shop1 = Task(user_id=user.id, title="Milch", category="shopping", priority=3, status="todo")
        shop2 = Task(user_id=user.id, title="Eier", category="shopping", priority=3, status="todo")
        shop3 = Task(user_id=user.id, title="Proteinpulver", category="shopping", priority=3, status="todo")
        session.add(shop1)
        session.add(shop2)
        session.add(shop3)
        await session.flush()
        print(f"✅ Tasks erstellt (inkl. 3 Shopping-Items)")

        # ─── Routines ─────────────────────────────────────────────────────────
        r_supplements = Routine(
            user_id=user.id,
            title="Supplements",
            frequency_human="Täglich",
            schedule_cron="0 8 * * *",
            status="active",
        )
        r_linkedin = Routine(
            user_id=user.id,
            title="LinkedIn Post",
            frequency_human="Jeden Dienstag",
            schedule_cron="0 9 * * 2",
            linked_key_result_id=kr_linkedin.id,
            status="active",
        )
        r_mealprep = Routine(
            user_id=user.id,
            title="Meal Prep",
            frequency_human="Jeden Sonntag",
            schedule_cron="0 11 * * 0",
            status="active",
        )
        session.add(r_supplements)
        session.add(r_linkedin)
        session.add(r_mealprep)
        await session.flush()
        print(f"✅ 3 Routinen erstellt")

        # ─── Calendar Events ──────────────────────────────────────────────────
        tomorrow = datetime.now().replace(hour=18, minute=0, second=0) + timedelta(days=1)
        day_after = datetime.now().replace(hour=14, minute=0, second=0) + timedelta(days=2)

        ev1 = CalendarEvent(
            user_id=user.id,
            title="Training",
            start_time=tomorrow,
            end_time=tomorrow + timedelta(hours=1),
            event_type="training",
            ical_uid=f"{uuid.uuid4()}@personal-os",
        )
        ev2 = CalendarEvent(
            user_id=user.id,
            title="Meeting mit Team",
            start_time=day_after,
            end_time=day_after + timedelta(hours=1),
            event_type="meeting",
            ical_uid=f"{uuid.uuid4()}@personal-os",
        )
        session.add(ev1)
        session.add(ev2)
        await session.flush()
        print(f"✅ 2 Kalender-Events erstellt")

        # ─── Brain Dump ───────────────────────────────────────────────────────
        bd = BrainDump(
            user_id=user.id,
            raw_input="Podcast starten? Könnte ein guter Content-Kanal sein.",
            processed=False,
        )
        session.add(bd)

        # ─── Logs ─────────────────────────────────────────────────────────────
        log_workout = Log(
            user_id=user.id,
            key_result_id=kr_training.id,
            log_type="workout",
            data={"exercise": "Bankdrücken", "weight": 80, "reps": 8, "sets": 3},
            raw_input="Bankdrücken 80kg×8×3",
            logged_at=datetime.utcnow() - timedelta(hours=2),
        )
        log_water = Log(
            user_id=user.id,
            log_type="water",
            data={"amount": 1.5},
            raw_input="1.5L Wasser",
            logged_at=datetime.utcnow() - timedelta(hours=1),
        )
        session.add(log_workout)
        session.add(log_water)

        await session.commit()
        print(f"\n🎉 Seed-Daten erfolgreich erstellt!")
        print(f"   User Telegram ID: {telegram_id}")
        print(f"   Start den Bot und schreib ihm!")


if __name__ == "__main__":
    asyncio.run(seed())
