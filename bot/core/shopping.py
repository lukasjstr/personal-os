"""Shopping list management — tasks with category='shopping'."""
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from bot.core.tasks import (
    complete_task,
    create_task,
    get_open_shopping_items,
)
from bot.database.models import Task


async def add_shopping_item(session: AsyncSession, user_id: int, title: str) -> Task:
    """Add an item to the shopping list (creates a task with category='shopping')."""
    return await create_task(
        session,
        user_id=user_id,
        title=title,
        category="shopping",
        priority=3,
    )


async def get_shopping_list(session: AsyncSession, user_id: int) -> list[Task]:
    """Get all open shopping items."""
    return await get_open_shopping_items(session, user_id)


async def complete_shopping(
    session: AsyncSession,
    user_id: int,
    item_ids: Optional[list[int]] = None,
) -> int:
    """Mark shopping items as done. If item_ids is None/empty, complete all."""
    if item_ids:
        count = 0
        for item_id in item_ids:
            task = await complete_task(session, user_id, item_id)
            if task:
                count += 1
        return count
    else:
        items = await get_open_shopping_items(session, user_id)
        for item in items:
            await complete_task(session, user_id, item.id)
        return len(items)


async def get_shopping_summary(session: AsyncSession, user_id: int) -> str:
    """Return a formatted shopping list string."""
    items = await get_open_shopping_items(session, user_id)
    if not items:
        return "🛒 Einkaufsliste ist leer."
    lines = [f"🛒 *Einkaufsliste* ({len(items)} Items)\n"]
    for item in items:
        lines.append(f"  ☐ {item.title} (#{item.id})")
    return "\n".join(lines)
