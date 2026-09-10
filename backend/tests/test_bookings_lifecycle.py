from typing import Any

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Booking, BookingStatus, Scooter, ScooterStatus
from app.realtime.hub import hub
from tests.test_bookings import headers, make_scooter, make_user


class FakeSocket:
    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []

    async def send_json(self, message: dict[str, Any]) -> None:
        self.sent.append(message)

    def of_type(self, event_type: str) -> list[dict[str, Any]]:
        return [m for m in self.sent if m["type"] == event_type]


async def test_active_booking_endpoint_returns_null_then_the_booking(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user = await make_user(db_session)
    await make_scooter(db_session)

    before = await client.get("/api/bookings/active", headers=headers(user))
    created = await client.post(
        "/api/bookings", json={"scooter_code": "KG-B1"}, headers=headers(user)
    )
    after = await client.get("/api/bookings/active", headers=headers(user))

    assert before.status_code == 200 and before.json() is None
    assert created.status_code == 201
    assert after.status_code == 200
    assert after.json()["id"] == created.json()["id"]
    assert after.json()["scooter_code"] == "KG-B1"


async def test_creating_a_booking_notifies_the_users_other_tabs(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user = await make_user(db_session)
    await make_scooter(db_session)
    tab = FakeSocket()
    hub.register(tab)  # type: ignore[arg-type]
    hub.identify(tab, user.id)  # type: ignore[arg-type]
    try:
        response = await client.post(
            "/api/bookings", json={"scooter_code": "KG-B1"}, headers=headers(user)
        )
    finally:
        hub.unregister(tab)  # type: ignore[arg-type]

    assert response.status_code == 201
    created = tab.of_type("booking.created")
    assert len(created) == 1
    assert created[0]["booking"]["id"] == response.json()["id"]


async def test_cancel_releases_the_scooter_and_notifies_the_user(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user = await make_user(db_session)
    await make_scooter(db_session)
    booking_id = (
        await client.post("/api/bookings", json={"scooter_code": "KG-B1"}, headers=headers(user))
    ).json()["id"]
    tab = FakeSocket()
    hub.register(tab)  # type: ignore[arg-type]
    hub.identify(tab, user.id)  # type: ignore[arg-type]
    try:
        response = await client.post(f"/api/bookings/{booking_id}/cancel", headers=headers(user))
    finally:
        hub.unregister(tab)  # type: ignore[arg-type]

    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"
    db_session.expire_all()
    scooter = await db_session.scalar(select(Scooter).where(Scooter.code == "KG-B1"))
    booking = await db_session.get(Booking, booking_id)
    assert scooter is not None and scooter.status is ScooterStatus.AVAILABLE
    assert booking is not None and booking.status is BookingStatus.CANCELLED
    assert booking.ended_at is not None
    assert tab.of_type("scooter.updated")[0]["scooter"]["status"] == "available"
    assert tab.of_type("booking.cancelled")[0]["booking"]["id"] == booking_id
    active = await client.get("/api/bookings/active", headers=headers(user))
    assert active.json() is None


async def test_only_the_owner_can_cancel(client: AsyncClient, db_session: AsyncSession) -> None:
    owner = await make_user(db_session, "Owner")
    stranger = await make_user(db_session, "Stranger")
    await make_scooter(db_session)
    booking_id = (
        await client.post("/api/bookings", json={"scooter_code": "KG-B1"}, headers=headers(owner))
    ).json()["id"]

    response = await client.post(f"/api/bookings/{booking_id}/cancel", headers=headers(stranger))

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "not_your_booking"
    db_session.expire_all()
    booking = await db_session.get(Booking, booking_id)
    assert booking is not None and booking.status is BookingStatus.ACTIVE


async def test_cancelling_twice_or_unknown_booking_fails_clearly(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user = await make_user(db_session)
    await make_scooter(db_session)
    booking_id = (
        await client.post("/api/bookings", json={"scooter_code": "KG-B1"}, headers=headers(user))
    ).json()["id"]
    assert (
        await client.post(f"/api/bookings/{booking_id}/cancel", headers=headers(user))
    ).status_code == 200

    again = await client.post(f"/api/bookings/{booking_id}/cancel", headers=headers(user))
    unknown = await client.post("/api/bookings/999999/cancel", headers=headers(user))

    assert again.status_code == 409
    assert again.json()["detail"]["code"] == "booking_not_active"
    assert unknown.status_code == 404
