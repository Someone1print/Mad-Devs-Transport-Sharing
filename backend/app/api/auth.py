from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.account_checks import address_problem, get_domain_checker
from app.api.deps import SESSION_COOKIE, CurrentToken, CurrentUser, api_error, cookie_max_age
from app.core import clock
from app.core.config import settings
from app.db.session import get_db
from app.schemas.auth import AuthOut, LoginIn, RegisterIn
from app.schemas.user import UserOut
from app.services.auth import AuthError, authenticate, password_problem, register, revoke_session
from app.services.mail_domain import DomainChecker

router = APIRouter()


def set_session_cookie(response: Response, token: str) -> None:
    """The browser's copy of the token: HttpOnly (no script can read it), SameSite=Lax (not
    sent on cross-site POSTs, so no CSRF token is needed), Secure behind HTTPS."""
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=cookie_max_age(),
        httponly=True,
        samesite="lax",
        secure=settings.session_cookie_secure,
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/")


def auth_error(exc: AuthError, status_code: int) -> HTTPException:
    return HTTPException(status_code, detail=api_error(exc.code, str(exc)))


def invalid_password(problem: str) -> HTTPException:
    return HTTPException(
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail={
            **api_error("invalid_password", f"Password problem: {problem}"),
            "problem": problem,
        },
    )


@router.post("/auth/register", status_code=status.HTTP_201_CREATED, summary="Create an account")
async def register_account(
    payload: RegisterIn,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db)],
    checker: Annotated[DomainChecker, Depends(get_domain_checker)],
) -> AuthOut:
    """E-mail (format and mail domain) and password (length) are checked here, uniqueness in
    the service; a legacy row without a password is claimed instead of creating a new one."""
    if (problem := password_problem(payload.password)) is not None:
        raise invalid_password(problem)
    await address_problem(payload.email, checker)  # raises 422 invalid_email; asks DNS last
    try:
        user, token = await register(
            session,
            name=payload.name,
            email=payload.email,
            password=payload.password,
            now=clock.now(),
        )
    except AuthError as exc:
        raise auth_error(exc, status.HTTP_409_CONFLICT) from exc
    set_session_cookie(response, token)
    return AuthOut(user=UserOut.model_validate(user), token=token)


@router.post("/auth/login", summary="Sign in")
async def login(
    payload: LoginIn, response: Response, session: Annotated[AsyncSession, Depends(get_db)]
) -> AuthOut:
    """401 `invalid_credentials` for a wrong password or an unknown address alike;
    401 `password_not_set` for an account from before passwords existed."""
    try:
        user, token = await authenticate(
            session, email=payload.email, password=payload.password, now=clock.now()
        )
    except AuthError as exc:
        raise auth_error(exc, status.HTTP_401_UNAUTHORIZED) from exc
    set_session_cookie(response, token)
    return AuthOut(user=UserOut.model_validate(user), token=token)


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT, summary="Sign out")
async def logout(
    user: CurrentUser,
    token: CurrentToken,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Deletes this device's session and clears the cookie; other devices stay signed in."""
    del user  # the dependency only proves the token is valid
    await revoke_session(session, token)
    await session.commit()
    clear_session_cookie(response)
