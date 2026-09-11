from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser
from app.db.session import get_db
from app.models import User
from app.schemas.user import UserCreate, UserOut

router = APIRouter()


@router.post("/users", status_code=status.HTTP_201_CREATED, summary="Register by name")
async def create_user(
    payload: UserCreate, session: Annotated[AsyncSession, Depends(get_db)]
) -> UserOut:
    """Create a user from a display name; the client keeps the returned id."""
    user = User(name=payload.name)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return UserOut.model_validate(user)


@router.get("/users/me", summary="Current user")
async def get_me(user: CurrentUser) -> UserOut:
    """Validate the stored id: 401 means the client must register again."""
    return UserOut.model_validate(user)
