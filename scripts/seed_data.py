"""Seed test data into the database for development."""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot.database.connection import AsyncSessionLocal
from bot.database.models import Objective, KeyResult, Task, Routine, User
import secrets


async def seed() -> None:
    async with AsyncSessionLocal() as session:
        # Create test user (use your real Telegram ID here)
        user = User(
            telegram_id=999999999,
            telegram_username="testuser",
            first_name="Test",
            timezone="Europe/Berlin",
            api_token=secrets.token_urlsafe(32),
        )
        session.add(user)
        await session.flush()
        print(f"Created user #{user.id} (telegram_id=999999999)")
        print(f"API Token: {user.api_token}")

        # Objective 1: Fitness
        fitness = Objective(
            user_id=user.id,
            title="Fitter werden",
            category="fitness",
            description="Körperliche Fitness steigern",
        )
        session.add(fitness)
        await session.flush()

        kr_training = KeyResult(
            objective_id=fitness.id,
            user_id=user.id,
            title="4x Training pro Woche",
            metric_type="number",
            target_value=4.0,
            unit="Trainings",
            frequency="weekly",
        )
        kr_water = KeyResult(
            objective_id=fitness.id,
            user_id=user.id,
            title="3L Wasser täglich",
            metric_type="number",
            target_value=3.0,
            unit="Liter",
            frequency="daily",
        )
        session.add(kr_training)
        session.add(kr_water)
        await session.flush()

        # Objective 2: Business
        business = Objective(
            user_id=user.id,
            title="Business aufbauen",
            category="business",
            description="Online-Business skalieren",
        )
        session.add(business)
        await session.flush()

        kr_linkedin = KeyResult(
            objective_id=business.id,
            user_id=user.id,
            title="10 LinkedIn Posts diesen Monat",
            metric_type="number",
            target_value=10.0,
            current_value=3.0,
            unit="Posts",
            frequency="monthly",
        )
        session.add(kr_linkedin)
        await session.flush()

        # Tasks
        tasks = [
            Task(user_id=user.id, title="Hero Section schreiben", priority=5, key_result_id=kr_linkedin.id),
            Task(user_id=user.id, title="Testimonials sammeln", priority=4),
            Task(user_id=user.id, title="CTA testen", priority=3),
        ]
        for t in tasks:
            session.add(t)

        # Routines
        routines = [
            Routine(
                user_id=user.id,
                title="Supplements",
                schedule_cron="0 8 * * *",
                frequency_human="Täglich 8:00",
                linked_key_result_id=kr_water.id,
            ),
            Routine(
                user_id=user.id,
                title="10min Journaling",
                schedule_cron="0 22 * * *",
                frequency_human="Täglich 22:00",
            ),
            Routine(
                user_id=user.id,
                title="LinkedIn Post schreiben",
                schedule_cron="0 9 * * 2",
                frequency_human="Jeden Dienstag 9:00",
                linked_key_result_id=kr_linkedin.id,
            ),
        ]
        for r in routines:
            session.add(r)

        await session.commit()
        print("Seed data created successfully!")
        print(f"\nObjectives: Fitness (#{fitness.id}), Business (#{business.id})")
        print(f"Key Results: Training (#{kr_training.id}), Wasser (#{kr_water.id}), LinkedIn (#{kr_linkedin.id})")


if __name__ == "__main__":
    asyncio.run(seed())
