from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models import User

USER_ID_HEADER = "X-User-Id"


def api_error(code: str, message: str) -> dict[str, str]:
    """Error payload shape used in HTTPException details: a machine code plus a human message."""
    return {"code": code, "message": message}


async def get_current_user(
    session: Annotated[AsyncSession, Depends(get_db)],
    x_user_id: Annotated[str | None, Header(alias=USER_ID_HEADER)] = None,
) -> User:
    """Identify the caller by the `X-User-Id` header (no authentication in this demo)."""
    unauthorized = HTTPException(
        status.HTTP_401_UNAUTHORIZED,
        detail=api_error("user_required", "Send a known user id in the X-User-Id header"),
    )
    if x_user_id is None or not x_user_id.isdigit():
        raise unauthorized
    user = await session.get(User, int(x_user_id))
    if user is None:
        raise unauthorized
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
