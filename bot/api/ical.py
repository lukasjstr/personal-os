"""iCal feed endpoint."""
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from sqlalchemy import and_, select

from bot.core.calendar import generate_ical, get_upcoming_events
from bot.database.connection import get_session
from bot.database.models import CalendarEvent, Routine, User

router = APIRouter()


@router.get("/cal/{user_token}.ics")
async def get_ical_feed(user_token: str) -> Response:
    """Generate and serve an iCal feed for a user."""
    async with get_session() as session:
        result = await session.execute(
            select(User).where(User.api_token == user_token)
        )
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="Feed not found")

        events = await get_upcoming_events(session, user.id, limit=100)

    ical_content = generate_ical(events, user_token)

    return Response(
        content=ical_content,
        media_type="text/calendar; charset=utf-8",
        headers={
            "Content-Disposition": "attachment; filename=personal-os.ics",
            "Cache-Control": "no-cache",
        },
    )
