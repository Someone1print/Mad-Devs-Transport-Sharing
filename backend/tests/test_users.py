import dns.resolver
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.users import get_domain_checker
from app.main import app
from app.services.mail_domain import DomainChecker
from tests.test_auth import PASSWORD, bearer, register
from tests.test_bookings import make_scooter
from tests.test_mail_domain import FakeResolver, Rdata
from tests.test_receipt_email_and_history import finished_ride


async def test_me_returns_the_user_behind_the_session(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user, token = await register(client, name="  Айбек  ", email="aibek@gmail.com")

    response = await client.get("/api/users/me", headers=bearer(token))

    assert response.status_code == 200
    assert response.json() == user
    assert user["name"] == "Айбек" and isinstance(user["id"], int) and "created_at" in user


async def test_me_without_a_session_is_unauthorized(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    response = await client.get("/api/users/me")

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "user_required"


async def test_email_can_be_changed_and_is_validated(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    _, token = await register(client, email="dana@gmail.com")
    client.cookies.clear()  # act through the bearer header only, like a script would
    hdrs = bearer(token)

    saved = await client.patch("/api/users/me", json={"email": "  Dana2@gmail.com "}, headers=hdrs)
    me = await client.get("/api/users/me", headers=hdrs)
    rejected = await client.patch("/api/users/me", json={"email": "dana@example"}, headers=hdrs)
    still_me = await client.get("/api/users/me", headers=hdrs)
    anonymous = await client.patch("/api/users/me", json={"email": "x@y.z"})

    assert saved.status_code == 200
    assert saved.json()["email"] == "dana2@gmail.com"  # trimmed and lower-cased: it is the login
    assert me.json()["email"] == "dana2@gmail.com"
    assert rejected.status_code == 422
    assert rejected.json()["detail"]["code"] == "invalid_email"
    assert rejected.json()["detail"]["problem"] == "domain"
    assert still_me.json()["email"] == "dana2@gmail.com"  # a rejected value changes nothing
    assert anonymous.status_code == 401
    signed_in = await client.post(
        "/api/auth/login", json={"email": "dana2@gmail.com", "password": PASSWORD}
    )
    assert signed_in.status_code == 200


async def test_receipt_goes_to_the_entered_address_or_the_stub(
    client: AsyncClient, db_session: AsyncSession, clock
) -> None:
    first = await finished_ride(client, db_session, clock, seconds=60)
    hdrs = first["_headers"]
    await client.patch("/api/users/me", json={"email": "rider@example.com"}, headers=hdrs)
    await make_scooter(db_session, code="KG-B2")
    booking = (
        await client.post("/api/bookings", json={"scooter_code": "KG-B2"}, headers=hdrs)
    ).json()
    ride_id = (
        await client.post("/api/rides", json={"booking_id": booking["id"]}, headers=hdrs)
    ).json()["id"]
    clock.set(200)
    await client.post(f"/api/rides/{ride_id}/finish", headers=hdrs)

    emails = (await client.get("/api/emails", headers=hdrs)).json()

    # newest first: the second receipt went to the entered address, the first to the stub
    assert [e["to_address"] for e in emails] == ["rider@example.com", "rider@example.invalid"]


async def test_saving_or_registering_an_address_checks_that_its_domain_receives_mail(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """The DNS check runs after the format check, at registration and on change; the app's
    default checker is switched off in tests, so a fake resolver is injected here."""
    resolver = FakeResolver({"MX": dns.resolver.NXDOMAIN()})
    app.dependency_overrides[get_domain_checker] = lambda: DomainChecker(
        enabled=True, timeout=2.0, resolver=resolver
    )
    try:
        typo_at_signup = await client.post(
            "/api/auth/register",
            json={"name": "Dana", "email": "dana@gmail.con", "password": PASSWORD},
        )
        resolver.answers["MX"] = [Rdata("alt1.gmail-smtp-in.l.google.com.")]
        _, token = await register(client, email="dana@gmail.com")
        hdrs = bearer(token)
        resolver.answers["MX"] = dns.resolver.NXDOMAIN()

        typo = await client.patch("/api/users/me", json={"email": "dana@gmail.con"}, headers=hdrs)
        bad_format = await client.patch("/api/users/me", json={"email": "dana@x"}, headers=hdrs)
        queries_so_far = [q[0] for q in resolver.queries]
        resolver.answers["MX"] = [Rdata("alt1.gmail-smtp-in.l.google.com.")]
        saved = await client.patch("/api/users/me", json={"email": "dana2@gmail.com"}, headers=hdrs)
    finally:
        app.dependency_overrides.pop(get_domain_checker, None)

    assert typo_at_signup.status_code == 422
    assert typo_at_signup.json()["detail"]["problem"] == "no_mail_server"
    assert typo.status_code == 422
    assert typo.json()["detail"]["code"] == "invalid_email"
    assert typo.json()["detail"]["problem"] == "no_mail_server"
    assert bad_format.json()["detail"]["problem"] == "domain"
    assert queries_so_far == [
        "gmail.con",
        "gmail.com",
        "gmail.con",
    ]  # a format problem never reaches DNS
    assert saved.status_code == 200 and saved.json()["email"] == "dana2@gmail.com"
