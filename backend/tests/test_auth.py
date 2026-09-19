"""Accounts: registration, sign-in, sessions, sign-out, password change, legacy accounts."""

import asyncio
from datetime import UTC, datetime, timedelta

from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import User, UserSession
from app.services.auth import hash_password, password_problem
from tests.test_bookings import headers, make_scooter, make_user

PASSWORD = "correct horse"


async def register(
    client: AsyncClient, name: str = "Dana", email: str = "dana@gmail.com", password: str = PASSWORD
) -> tuple[dict, str]:
    response = await client.post(
        "/api/auth/register", json={"name": name, "email": email, "password": password}
    )
    assert response.status_code == 201, response.text
    body = response.json()
    return body["user"], body["token"]


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_password_rules_are_length_only() -> None:
    assert password_problem("1234567") == "too_short"
    assert password_problem("12345678") is None
    assert password_problem("пароль!!") is None  # 8 code points, nothing about characters
    assert password_problem("x" * 128) is None
    assert password_problem("x" * 129) == "too_long"


async def test_register_returns_the_user_and_a_token_and_sets_the_session_cookie(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    response = await client.post(
        "/api/auth/register",
        json={"name": "  Dana ", "email": " Dana@Gmail.com ", "password": PASSWORD},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["user"]["name"] == "Dana"
    assert body["user"]["email"] == "dana@gmail.com"  # normalised: trimmed, lower-case
    assert body["user"]["mail_address"] == "dana@gmail.com"
    assert "password" not in body["user"] and "password_hash" not in body["user"]
    assert len(body["token"]) >= 32
    cookie = response.headers["set-cookie"]
    assert cookie.startswith("session=") and "HttpOnly" in cookie and "SameSite=lax" in cookie
    stored = await db_session.scalar(select(User).where(User.id == body["user"]["id"]))
    assert stored is not None and stored.password_hash is not None
    assert PASSWORD not in stored.password_hash  # hashed, never the clear text
    assert stored.password_hash.startswith("$argon2id$")


async def test_register_validates_the_email_and_the_password(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    bad_email = await client.post(
        "/api/auth/register", json={"name": "Dana", "email": "dana@gmail", "password": PASSWORD}
    )
    short = await client.post(
        "/api/auth/register",
        json={"name": "Dana", "email": "dana@gmail.com", "password": "1234567"},
    )
    blank_name = await client.post(
        "/api/auth/register", json={"name": "  ", "email": "dana@gmail.com", "password": PASSWORD}
    )

    assert bad_email.status_code == 422
    assert bad_email.json()["detail"]["code"] == "invalid_email"
    assert bad_email.json()["detail"]["problem"] == "domain"
    assert short.status_code == 422
    assert short.json()["detail"]["code"] == "invalid_password"
    assert short.json()["detail"]["problem"] == "too_short"
    assert blank_name.status_code == 422
    assert await db_session.scalar(select(User)) is None  # nothing was created


async def test_register_refuses_an_email_that_already_has_a_password(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await register(client, email="dana@gmail.com")

    again = await client.post(
        "/api/auth/register",
        json={"name": "Dana 2", "email": "DANA@gmail.com", "password": PASSWORD},
    )

    assert again.status_code == 409
    assert again.json()["detail"]["code"] == "email_taken"


async def test_login_with_the_right_and_the_wrong_password(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user, _ = await register(client)

    ok = await client.post(
        "/api/auth/login", json={"email": "DANA@gmail.com ", "password": PASSWORD}
    )
    wrong = await client.post(
        "/api/auth/login", json={"email": "dana@gmail.com", "password": "nope!"}
    )
    unknown = await client.post(
        "/api/auth/login", json={"email": "nobody@gmail.com", "password": PASSWORD}
    )

    assert ok.status_code == 200
    assert ok.json()["user"]["id"] == user["id"]
    assert ok.headers["set-cookie"].startswith("session=")
    me = await client.get("/api/users/me", headers=bearer(ok.json()["token"]))
    assert me.status_code == 200 and me.json()["id"] == user["id"]
    assert wrong.status_code == 401 and wrong.json()["detail"]["code"] == "invalid_credentials"
    # the same answer for an unknown address: sign-in does not reveal who has an account
    assert unknown.status_code == 401 and unknown.json()["detail"] == wrong.json()["detail"]


async def test_the_cookie_alone_authenticates_the_browser(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await register(client)  # httpx keeps the Set-Cookie in its jar, like a browser

    me = await client.get("/api/users/me")

    assert me.status_code == 200 and me.json()["email"] == "dana@gmail.com"


async def test_logout_revokes_the_session_and_clears_the_cookie(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    _, token = await register(client)

    logout = await client.post("/api/auth/logout", headers=bearer(token))
    after = await client.get("/api/users/me", headers=bearer(token))
    client.cookies.clear()
    without_cookie = await client.get("/api/users/me")

    assert logout.status_code == 204
    assert (
        'session=""' in logout.headers["set-cookie"] or "Max-Age=0" in logout.headers["set-cookie"]
    )
    assert after.status_code == 401
    assert without_cookie.status_code == 401
    assert await db_session.scalar(select(UserSession)) is None


async def test_a_foreign_user_id_can_no_longer_be_substituted(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Whatever the client sends about ids, the session decides: another user's ride and
    mailbox stay out of reach, and the old X-User-Id header means nothing."""
    dana, dana_token = await register(client, name="Dana", email="dana@gmail.com")
    client.cookies.clear()
    aibek, aibek_token = await register(client, name="Aibek", email="aibek@gmail.com")
    client.cookies.clear()
    scooter = await make_scooter(db_session, "KG-A1")
    booking = await client.post(
        "/api/bookings", json={"scooter_code": scooter.code}, headers=bearer(dana_token)
    )
    ride = await client.post(
        "/api/rides", json={"booking_id": booking.json()["id"]}, headers=bearer(dana_token)
    )
    ride_id = ride.json()["id"]

    spoofed_header = await client.get(
        "/api/users/me", headers={**bearer(aibek_token), "X-User-Id": str(dana["id"])}
    )
    header_only = await client.get("/api/users/me", headers={"X-User-Id": str(dana["id"])})
    their_ride = await client.get(f"/api/rides/{ride_id}", headers=bearer(aibek_token))
    their_active = await client.get("/api/rides/active", headers=bearer(aibek_token))
    their_mail = await client.get("/api/emails", headers=bearer(aibek_token))
    garbage_token = await client.get("/api/users/me", headers=bearer("not-a-session-token"))

    assert spoofed_header.status_code == 200 and spoofed_header.json()["id"] == aibek["id"]
    assert header_only.status_code == 401
    assert their_ride.status_code == 403
    assert their_active.status_code == 200 and their_active.json() is None
    assert their_mail.status_code == 200 and their_mail.json() == []
    assert garbage_token.status_code == 401


async def test_password_change_needs_the_current_one_and_signs_out_other_devices(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    _, phone = await register(client)
    laptop = (
        await client.post("/api/auth/login", json={"email": "dana@gmail.com", "password": PASSWORD})
    ).json()["token"]

    wrong = await client.post(
        "/api/users/me/password",
        json={"current_password": "nope!", "new_password": "new password 1"},
        headers=bearer(laptop),
    )
    short = await client.post(
        "/api/users/me/password",
        json={"current_password": PASSWORD, "new_password": "short"},
        headers=bearer(laptop),
    )
    changed = await client.post(
        "/api/users/me/password",
        json={"current_password": PASSWORD, "new_password": "new password 1"},
        headers=bearer(laptop),
    )
    laptop_still_in = await client.get("/api/users/me", headers=bearer(laptop))
    phone_signed_out = await client.get("/api/users/me", headers=bearer(phone))
    old_password = await client.post(
        "/api/auth/login", json={"email": "dana@gmail.com", "password": PASSWORD}
    )
    new_password = await client.post(
        "/api/auth/login", json={"email": "dana@gmail.com", "password": "new password 1"}
    )

    # 403, not 401: the session is valid, and a 401 would sign the client out
    assert wrong.status_code == 403 and wrong.json()["detail"]["code"] == "wrong_password"
    assert short.status_code == 422 and short.json()["detail"]["problem"] == "too_short"
    assert changed.status_code == 200
    assert laptop_still_in.status_code == 200
    assert phone_signed_out.status_code == 401
    assert old_password.status_code == 401 and new_password.status_code == 200


async def test_an_expired_session_is_refused(client: AsyncClient, db_session: AsyncSession) -> None:
    _, token = await register(client)
    stored = await db_session.scalar(select(UserSession))
    assert stored is not None
    stored.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    await db_session.commit()

    me = await client.get("/api/users/me", headers=bearer(token))

    assert me.status_code == 401
    assert await db_session.scalar(select(UserSession)) is None  # removed on the way


async def test_registration_claims_a_legacy_account_by_email_and_keeps_its_history(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """A row without a password is an account waiting to be registered: the rides stay."""
    legacy = await make_user(db_session, "Дана", legacy=True)
    legacy.email = "Dana@Gmail.com"
    await db_session.commit()
    scooter = await make_scooter(db_session, "KG-L1")
    booking = await client.post(
        "/api/bookings", json={"scooter_code": scooter.code}, headers=headers(legacy)
    )
    assert booking.status_code == 201

    user, token = await register(client, name="Dana Registered", email="dana@gmail.com")

    assert user["id"] == legacy.id
    assert user["name"] == "Dana Registered"  # the name entered at registration wins
    active = await client.get("/api/bookings/active", headers=bearer(token))
    assert active.json() is not None and active.json()["scooter_code"] == "KG-L1"
    await db_session.refresh(legacy)
    assert legacy.password_hash is not None


async def test_registration_claims_a_legacy_account_by_name_when_it_has_no_email(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    legacy = await make_user(db_session, "Айбек", legacy=True)
    await make_user(db_session, "Дана", legacy=True)  # a different name: not claimed

    user, _ = await register(client, name=" Айбек ", email="aibek@gmail.com")

    assert user["id"] == legacy.id and user["email"] == "aibek@gmail.com"


async def test_registration_does_not_guess_between_two_legacy_accounts_with_one_name(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    first = await make_user(db_session, "Айбек", legacy=True)
    second = await make_user(db_session, "Айбек", legacy=True)

    user, _ = await register(client, name="Айбек", email="aibek@gmail.com")

    assert user["id"] not in (first.id, second.id)


async def test_login_into_a_legacy_account_explains_that_it_has_no_password(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    legacy = await make_user(db_session, "Дана", legacy=True)
    legacy.email = "dana@gmail.com"
    await db_session.commit()

    response = await client.post(
        "/api/auth/login", json={"email": "dana@gmail.com", "password": PASSWORD}
    )

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "password_not_set"


async def test_changing_the_email_keeps_it_unique_among_registered_accounts(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    _, dana = await register(client, name="Dana", email="dana@gmail.com")
    client.cookies.clear()
    await register(client, name="Aibek", email="aibek@gmail.com")

    taken = await client.patch(
        "/api/users/me", json={"email": "AIBEK@gmail.com"}, headers=bearer(dana)
    )
    cleared = await client.patch("/api/users/me", json={"email": ""}, headers=bearer(dana))
    changed = await client.patch(
        "/api/users/me", json={"email": "dana2@gmail.com"}, headers=bearer(dana)
    )

    assert taken.status_code == 409 and taken.json()["detail"]["code"] == "email_taken"
    assert cleared.status_code == 422  # the address is the login now: it cannot be empty
    assert changed.status_code == 200 and changed.json()["email"] == "dana2@gmail.com"


async def test_hash_password_never_repeats_itself() -> None:
    first, second = await hash_password(PASSWORD), await hash_password(PASSWORD)
    assert first != second  # a fresh salt every time


async def test_two_registrations_with_one_email_at_once_yield_one_account(
    client: AsyncClient, committed_db: async_sessionmaker[AsyncSession]
) -> None:
    """Both requests pass the uniqueness check before either commits; the partial unique index
    stops the second one, and it must surface as 409, not as a crash."""
    payload = {"name": "Dana", "email": "dana@gmail.com", "password": PASSWORD}
    responses = await asyncio.gather(
        *(client.post("/api/auth/register", json=payload) for _ in range(3))
    )

    assert sorted(r.status_code for r in responses) == [201, 409, 409]
    for response in responses:
        if response.status_code == 409:
            assert response.json()["detail"]["code"] == "email_taken"
    async with committed_db() as session:
        accounts = await session.scalar(
            select(func.count()).select_from(User).where(User.email == "dana@gmail.com")
        )
    assert accounts == 1


async def test_unauthenticated_password_change_and_logout_are_401(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    change = await client.post(
        "/api/users/me/password", json={"current_password": "a", "new_password": "b" * 8}
    )
    logout = await client.post("/api/auth/logout")

    assert change.status_code == 401 and logout.status_code == 401
