"""Authentication utilities for REST API."""
import secrets
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.connection import get_db
from bot.database.models import User

bearer_scheme = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    session: AsyncSession = Depends(get_db),
) -> User:
    """Validate Bearer token and return the authenticated user."""
    token = credentials.credentials
    result = await session.execute(
        select(User).where(User.api_token == token)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def generate_api_token(session: AsyncSession, user: User, force_new: bool = False) -> str:
    """Return the existing API token or generate a new one.

    Pass force_new=True to explicitly rotate the token.
    """
    if user.api_token and not force_new:
        return user.api_token
    token = secrets.token_urlsafe(32)
    user.api_token = token
    await session.flush()
    return token
