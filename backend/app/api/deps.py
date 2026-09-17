from typing import Annotated

from fastapi import Cookie, Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import clock
from app.core.config import settings
from app.db.session import get_db
from app.models import User
from app.services.auth import user_from_token

SESSION_COOKIE = "session"
BEARER_PREFIX = "Bearer "


def api_error(code: str, message: str) -> dict[str, str]:
    """Error payload shape used in HTTPException details: a machine code plus a human message."""
    return {"code": code, "message": message}


def session_token(authorization: str | None, cookie: str | None) -> str | None:
    """The session token a request carries: `Authorization: Bearer …` wins over the cookie."""
    if authorization and authorization.startswith(BEARER_PREFIX):
        return authorization.removeprefix(BEARER_PREFIX).strip() or None
    return cookie or None


async def get_current_user(
    session: Annotated[AsyncSession, Depends(get_db)],
    authorization: Annotated[str | None, Header()] = None,
    session_cookie: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> User:
    """Identify the caller by their session (bearer header or HttpOnly cookie) and nothing
    else: no header naming a user id is read anywhere."""
    unauthorized = HTTPException(
        status.HTTP_401_UNAUTHORIZED,
        detail=api_error("user_required", "Sign in to continue"),
    )
    token = session_token(authorization, session_cookie)
    if token is None:
        raise unauthorized
    user = await user_from_token(session, token, clock.now())
    if user is None:
        raise unauthorized
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def current_token(request: Request) -> str:
    """The token of the current request (after `get_current_user` accepted it)."""
    token = session_token(request.headers.get("authorization"), request.cookies.get(SESSION_COOKIE))
    assert token is not None
    return token


CurrentToken = Annotated[str, Depends(current_token)]


def cookie_max_age() -> int:
    return settings.session_ttl_days * 24 * 3600
