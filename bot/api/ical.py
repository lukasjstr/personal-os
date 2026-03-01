"""iCal feed endpoint — serves calendar data by ical_token from user settings."""
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from bot.core.calendar import generate_ical_for_user
from bot.core.user_settings import get_user_by_ical_token
from bot.database.connection import get_session

router = APIRouter()


@router.get("/cal/{user_token}.ics")
async def get_ical_feed(user_token: str) -> Response:
    """Generate and serve an iCal feed for a user.
    user_token is the ical_token stored in user.settings JSON.
    Subscribe this URL in Google/Apple Calendar.
    """
    async with get_session() as session:
        user = await get_user_by_ical_token(session, user_token)
        if not user:
            raise HTTPException(status_code=404, detail="Feed not found")

        ical_content = await generate_ical_for_user(session, user.id)

    return Response(
        content=ical_content,
        media_type="text/calendar; charset=utf-8",
        headers={
            "Content-Disposition": "attachment; filename=personal-os.ics",
            "Cache-Control": "no-cache, no-store",
        },
    )
