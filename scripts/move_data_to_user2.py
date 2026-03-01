"""Move all data from User1 (6118629820) to User2 (7118468255)."""
import asyncio
import secrets
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot.database.connection import AsyncSessionLocal
from bot.database.models import (
    User, Log, Task, Objective, Conversation,
    BrainDump, CalendarEvent, Routine, RoutineCompletion,
)
from sqlalchemy import select


async def move():
    async with AsyncSessionLocal() as s:
        r1 = await s.execute(select(User).where(User.telegram_id == 6118629820))
        user1 = r1.scalar_one()
        r2 = await s.execute(select(User).where(User.telegram_id == 7118468255))
        user2 = r2.scalar_one()

        print(f"User1 #{user1.id} tg=6118629820")
        print(f"User2 #{user2.id} tg=7118468255")

        for model in [Log, Task, Objective, Conversation, BrainDump, CalendarEvent, Routine, RoutineCompletion]:
            r = await s.execute(select(model).where(model.user_id == user1.id))
            items = r.scalars().all()
            if items:
                for item in items:
                    item.user_id = user2.id
                print(f"  Moved {len(items)} {model.__tablename__} -> User2")

        new_token = secrets.token_urlsafe(32)
        user2.api_token = new_token

        await s.commit()
        print(f"\nAll data now on User2 (tg=7118468255)")
        print(f"Dashboard token: {new_token}")


if __name__ == "__main__":
    asyncio.run(move())
