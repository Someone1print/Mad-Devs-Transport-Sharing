"""Accounts and sessions: passwords, sign-in, tokens, and the claiming of legacy rows.

Passwords are hashed with argon2id in a worker thread (a hash costs tens of milliseconds by
design). A session is a random token whose SHA-256 is stored in `user_sessions`; the token
itself goes to the client once (cookie and response body) and is never stored.

Rows without a password come from the time before accounts had one. They are "accounts waiting
to be registered": `register` claims such a row when its e-mail matches, or — for a row without
an e-mail — when its name matches exactly and no other legacy row has that name, so rides and
history survive the upgrade. Before the upgrade anyone could act as any of these rows, so
"first to register owns it" lowers nothing; afterwards the row is protected by a password.
"""

import asyncio
import hashlib
import logging
import secrets
from datetime import datetime, timedelta

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import User, UserSession

logger = logging.getLogger(__name__)

PASSWORD_MAX_LENGTH = 128  # long enough for any passphrase, short enough not to be a DoS
TOKEN_BYTES = 32

_hasher = PasswordHasher()


class AuthError(Exception):
    """A refused account operation; `code` is the API error code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def password_problem(value: str) -> str | None:
    """Why `value` is not an acceptable password: length only, no character classes."""
    if len(value) < settings.password_min_length:
        return "too_short"
    if len(value) > PASSWORD_MAX_LENGTH:
        return "too_long"
    return None


def normalize_email(value: str) -> str:
    """The stored and compared form of an address: trimmed and lower-cased."""
    return value.strip().lower()


async def hash_password(value: str) -> str:
    return await asyncio.to_thread(_hasher.hash, value)


async def verify_password(value: str, password_hash: str) -> bool:
    try:
        return await asyncio.to_thread(_hasher.verify, password_hash, value)
    except (VerifyMismatchError, InvalidHashError):
        return False


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def create_session(session: AsyncSession, user: User, now: datetime) -> str:
    """Open a session for the user; returns the token (not stored, only its hash is)."""
    token = secrets.token_urlsafe(TOKEN_BYTES)
    session.add(
        UserSession(
            user_id=user.id,
            token_hash=_token_hash(token),
            expires_at=now + timedelta(days=settings.session_ttl_days),
        )
    )
    await session.flush()
    return token


async def user_from_token(session: AsyncSession, token: str, now: datetime) -> User | None:
    """The user behind a session token, or None; an expired session is deleted on the way."""
    stored = await session.scalar(
        select(UserSession).where(UserSession.token_hash == _token_hash(token))
    )
    if stored is None:
        return None
    if stored.expires_at <= now:
        await session.delete(stored)
        await session.commit()
        return None
    return await session.get(User, stored.user_id)


async def revoke_session(session: AsyncSession, token: str) -> None:
    await session.execute(delete(UserSession).where(UserSession.token_hash == _token_hash(token)))


async def revoke_other_sessions(session: AsyncSession, user: User, keep_token: str) -> None:
    await session.execute(
        delete(UserSession).where(
            UserSession.user_id == user.id, UserSession.token_hash != _token_hash(keep_token)
        )
    )


async def registered_user_by_email(session: AsyncSession, email: str) -> User | None:
    """The account with a password that owns this address (unique among such accounts)."""
    return await session.scalar(
        select(User).where(func.lower(User.email) == email, User.password_hash.is_not(None))
    )


async def _legacy_account(session: AsyncSession, email: str, name: str) -> User | None:
    """A row without a password to claim: by e-mail first, else by an unambiguous name."""
    by_email = (
        await session.scalars(
            select(User)
            .where(func.lower(User.email) == email, User.password_hash.is_(None))
            .order_by(User.created_at.desc(), User.id.desc())
        )
    ).all()
    if by_email:
        if len(by_email) > 1:
            logger.warning(
                "%d legacy accounts share %s; claiming the latest (id %d)",
                len(by_email),
                email,
                by_email[0].id,
            )
        return by_email[0]
    by_name = (
        await session.scalars(
            select(User).where(
                User.name == name, User.email.is_(None), User.password_hash.is_(None)
            )
        )
    ).all()
    return by_name[0] if len(by_name) == 1 else None


async def register(
    session: AsyncSession, *, name: str, email: str, password: str, now: datetime
) -> tuple[User, str]:
    """Create the account (or claim a legacy row, see the module docstring) and sign it in.

    Callers validate the name, the e-mail format and domain, and the password first; here
    only uniqueness is checked. Returns the user and a session token.
    """
    email = normalize_email(email)
    if await registered_user_by_email(session, email) is not None:
        raise AuthError("email_taken", "An account with this e-mail already exists")
    password_hash = await hash_password(password)
    user = await _legacy_account(session, email, name)
    if user is None:
        user = User(name=name, email=email, password_hash=password_hash)
        session.add(user)
    else:
        logger.info("Legacy account %d claimed by %s", user.id, email)
        user.name, user.email, user.password_hash = name, email, password_hash
    try:
        await session.flush()
        token = await create_session(session, user, now)
        await session.commit()
    except IntegrityError as exc:
        # two registrations with one address at the same moment: both passed the check above,
        # the partial unique index lets exactly one through
        await session.rollback()
        raise AuthError("email_taken", "An account with this e-mail already exists") from exc
    await session.refresh(user)
    return user, token


async def authenticate(
    session: AsyncSession, *, email: str, password: str, now: datetime
) -> tuple[User, str]:
    """Sign in: one answer for a wrong password and an unknown address; a legacy row without
    a password gets its own code so the client can suggest registering with that address."""
    email = normalize_email(email)
    user = await registered_user_by_email(session, email)
    if user is None:
        legacy = await session.scalar(
            select(User).where(func.lower(User.email) == email, User.password_hash.is_(None))
        )
        if legacy is not None:
            raise AuthError(
                "password_not_set",
                "This account has no password yet: register with this e-mail to keep its history",
            )
        await verify_password(password, await _dummy_hash())  # constant-time-ish: no early exit
        raise AuthError("invalid_credentials", "Wrong e-mail or password")
    assert user.password_hash is not None
    if not await verify_password(password, user.password_hash):
        raise AuthError("invalid_credentials", "Wrong e-mail or password")
    token = await create_session(session, user, now)
    await session.commit()
    return user, token


_dummy: str | None = None


async def _dummy_hash() -> str:
    """A hash to verify against when the address is unknown, so both answers take as long."""
    global _dummy
    if _dummy is None:
        _dummy = await hash_password(secrets.token_urlsafe(16))
    return _dummy


async def change_password(
    session: AsyncSession, user: User, *, current: str, new: str, keep_token: str
) -> None:
    """Replace the password after checking the current one; other devices are signed out."""
    if user.password_hash is None or not await verify_password(current, user.password_hash):
        raise AuthError("wrong_password", "The current password is wrong")
    user.password_hash = await hash_password(new)
    await revoke_other_sessions(session, user, keep_token)
    await session.commit()
