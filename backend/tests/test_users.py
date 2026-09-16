from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.test_bookings import make_scooter
from tests.test_receipt_email_and_history import finished_ride


async def test_create_user_returns_id_and_name(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    response = await client.post("/api/users", json={"name": "  Айбек  "})

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Айбек"
    assert isinstance(body["id"], int)
    assert "created_at" in body


async def test_create_user_rejects_blank_name(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    response = await client.post("/api/users", json={"name": "   "})

    assert response.status_code == 422


async def test_me_returns_the_user_named_in_the_header(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    created = (await client.post("/api/users", json={"name": "Dana"})).json()

    response = await client.get("/api/users/me", headers={"X-User-Id": str(created["id"])})

    assert response.status_code == 200
    assert response.json() == created


async def test_me_without_header_is_unauthorized(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    response = await client.get("/api/users/me")

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "user_required"


async def test_me_with_unknown_or_malformed_id_is_unauthorized(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    unknown = await client.get("/api/users/me", headers={"X-User-Id": "999999"})
    malformed = await client.get("/api/users/me", headers={"X-User-Id": "abc"})

    assert unknown.status_code == 401
    assert malformed.status_code == 401


async def test_email_can_be_set_cleared_and_is_validated(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    created = (await client.post("/api/users", json={"name": "Dana"})).json()
    hdrs = {"X-User-Id": str(created["id"])}
    assert created["email"] is None

    saved = await client.patch("/api/users/me", json={"email": "  dana@example.com "}, headers=hdrs)
    me = await client.get("/api/users/me", headers=hdrs)
    rejected = await client.patch("/api/users/me", json={"email": "dana@example"}, headers=hdrs)
    still_me = await client.get("/api/users/me", headers=hdrs)
    cleared = await client.patch("/api/users/me", json={"email": ""}, headers=hdrs)
    anonymous = await client.patch("/api/users/me", json={"email": "x@y.z"})

    assert saved.status_code == 200
    assert saved.json()["email"] == "dana@example.com"  # trimmed, stored as typed otherwise
    assert me.json()["email"] == "dana@example.com"
    assert rejected.status_code == 422
    assert rejected.json()["detail"]["code"] == "invalid_email"
    assert rejected.json()["detail"]["problem"] == "domain"
    assert still_me.json()["email"] == "dana@example.com"  # a rejected value changes nothing
    assert cleared.status_code == 200 and cleared.json()["email"] is None
    assert anonymous.status_code == 401


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
