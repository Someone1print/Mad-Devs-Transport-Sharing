from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.account_checks import address_problem, get_domain_checker
from app.api.deps import CurrentToken, CurrentUser, api_error
from app.db.session import get_db
from app.schemas.auth import PasswordChangeIn
from app.schemas.user import UserEmailUpdate, UserOut
from app.services.auth import (
    AuthError,
    change_password,
    normalize_email,
    password_problem,
    registered_user_by_email,
)
from app.services.mail_domain import DomainChecker

__all__ = ["get_domain_checker", "router"]

router = APIRouter()


@router.get("/users/me", summary="Current user")
async def get_me(user: CurrentUser) -> UserOut:
    """The user behind the session; 401 means the client must sign in."""
    return UserOut.model_validate(user)


@router.patch("/users/me", summary="Change the e-mail (login and receipt address)")
async def update_email(
    payload: UserEmailUpdate,
    user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db)],
    checker: Annotated[DomainChecker, Depends(get_domain_checker)],
) -> UserOut:
    """422 `invalid_email` names the failed rule (`empty`, format, or the domain's mail server
    via DNS); 409 `email_taken` when another account signs in with it."""
    raw = payload.email or ""
    await address_problem(raw, checker)
    email = normalize_email(raw)
    owner = await registered_user_by_email(session, email)
    if owner is not None and owner.id != user.id:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=api_error("email_taken", "An account with this e-mail already exists"),
        )
    user.email = email
    await session.commit()
    await session.refresh(user)
    return UserOut.model_validate(user)


@router.post("/users/me/password", summary="Change the password")
async def update_password(
    payload: PasswordChangeIn,
    user: CurrentUser,
    token: CurrentToken,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> UserOut:
    """401 `wrong_password` when the current one does not match; 422 `invalid_password` for
    the new one; every other device of the user is signed out."""
    if (problem := password_problem(payload.new_password)) is not None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                **api_error("invalid_password", f"Password problem: {problem}"),
                "problem": problem,
            },
        )
    try:
        await change_password(
            session,
            user,
            current=payload.current_password,
            new=payload.new_password,
            keep_token=token,
        )
    except AuthError as exc:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, detail=api_error(exc.code, str(exc))
        ) from exc
    return UserOut.model_validate(user)
