from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, api_error
from app.db.session import get_db
from app.models import User
from app.schemas.user import UserCreate, UserEmailUpdate, UserOut
from app.services.mail import email_problem

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


@router.patch("/users/me", summary="Set or clear the e-mail for receipts")
async def update_email(
    payload: UserEmailUpdate, user: CurrentUser, session: Annotated[AsyncSession, Depends(get_db)]
) -> UserOut:
    """422 `invalid_email` names the failed rule; the client shows the matching hint."""
    email = (payload.email or "").strip() or None
    if email is not None and (problem := email_problem(email)) is not None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                **api_error("invalid_email", f"E-mail format problem: {problem}"),
                "problem": problem,
            },
        )
    user.email = email
    await session.commit()
    await session.refresh(user)
    return UserOut.model_validate(user)


@router.get("/users/me", summary="Current user")
async def get_me(user: CurrentUser) -> UserOut:
    """Validate the stored id: 401 means the client must register again."""
    return UserOut.model_validate(user)
