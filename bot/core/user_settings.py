"""User settings and toggle management."""
import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import User

DEFAULT_SETTINGS = {
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
}

BOOLEAN_TOGGLES = {
    "priorities_enabled",
    "review_enabled",
    "proactive_enabled",
    "reflection_enabled",
}

TIME_SETTINGS = {
    "morning_brief_time",
    "evening_review_time",
    "weekly_reflection_time",
    "shopping_reminder_time",
}


async def get_user(session: AsyncSession, user_id: int) -> Optional[User]:
    """Get user by internal ID."""
    result = await session.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def get_user_by_telegram(session: AsyncSession, telegram_id: int) -> Optional[User]:
    """Get user by Telegram ID."""
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    return result.scalar_one_or_none()


async def get_user_by_ical_token(session: AsyncSession, token: str) -> Optional[User]:
    """Find user by ical_token stored in settings JSON."""
    result = await session.execute(select(User))
    users = result.scalars().all()
    for user in users:
        if isinstance(user.settings, dict) and user.settings.get("ical_token") == token:
            return user
    return None


async def get_or_create_user(
    session: AsyncSession,
    telegram_id: int,
    username: Optional[str],
    first_name: Optional[str],
) -> User:
    """Get existing user or create with default settings."""
    import secrets
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()

    if not user:
        settings = dict(DEFAULT_SETTINGS)
        settings["ical_token"] = str(uuid.uuid4())
        user = User(
            telegram_id=telegram_id,
            telegram_username=username,
            first_name=first_name,
            is_active=True,
            settings=settings,
            api_token=secrets.token_urlsafe(32),
        )
        session.add(user)
        await session.flush()
    else:
        changed = False
        if username and user.telegram_username != username:
            user.telegram_username = username
            changed = True
        if first_name and user.first_name != first_name:
            user.first_name = first_name
            changed = True
        # Ensure settings has all default keys
        if not isinstance(user.settings, dict):
            user.settings = dict(DEFAULT_SETTINGS)
            user.settings["ical_token"] = str(uuid.uuid4())
            changed = True
        else:
            for k, v in DEFAULT_SETTINGS.items():
                if k not in user.settings:
                    user.settings[k] = v
                    changed = True
            if "ical_token" not in user.settings:
                user.settings["ical_token"] = str(uuid.uuid4())
                changed = True
        if changed:
            await session.flush()

    return user


async def update_setting(session: AsyncSession, user_id: int, key: str, value) -> User:
    """Update a single setting key."""
    user = await get_user(session, user_id)
    if not user:
        raise ValueError(f"User {user_id} not found")
    settings = dict(user.settings or {})
    settings[key] = value
    user.settings = settings
    await session.flush()
    return user


async def toggle_setting(session: AsyncSession, user_id: int, key: str) -> tuple[str, bool]:
    """Toggle a boolean setting. Returns (key, new_value)."""
    if key not in BOOLEAN_TOGGLES:
        raise ValueError(f"'{key}' is not a toggleable boolean setting")
    user = await get_user(session, user_id)
    if not user:
        raise ValueError(f"User {user_id} not found")
    settings = dict(user.settings or {})
    current = settings.get(key, True)
    new_value = not current
    settings[key] = new_value
    user.settings = settings
    await session.flush()
    return key, new_value


def format_settings(settings: dict) -> str:
    """Format user settings as a readable string."""
    on = "✅ AN"
    off = "❌ AUS"
    lines = [
        "⚙️ *Deine Einstellungen*\n",
        f"🎯 Prioritäten: {on if settings.get('priorities_enabled', True) else off}",
        f"📋 Abend-Review: {on if settings.get('review_enabled', True) else off}",
        f"📣 Proaktiv: {on if settings.get('proactive_enabled', True) else off}",
        f"🔮 Reflection: {on if settings.get('reflection_enabled', True) else off}",
        "",
        f"⏰ Morning Brief: {settings.get('morning_brief_time', '06:30')}",
        f"🌙 Evening Review: {settings.get('evening_review_time', '21:00')}",
        f"🛒 Shopping-Reminder: {settings.get('shopping_reminder_day', 'saturday')} {settings.get('shopping_reminder_time', '10:00')}",
        "",
        "Befehle: /toggle priorities | /toggle review | /toggle proactive | /toggle reflection",
        "/times morning HH:MM | /times evening HH:MM",
    ]
    return "\n".join(lines)
