"""HTTP layer of rides: payloads, status codes, events; time is controlled via app.core.clock."""

import asyncio
from typing import Any

from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import settings
from app.models import Ride, RideStatus, Scooter, ScooterStatus
from app.realtime.hub import hub
from app.seed import seed_zones
from tests.test_bookings import headers, make_scooter, make_user

INSIDE = (42.8756, 74.6036)
OUTSIDE = (42.8500, 74.6000)


class FakeSocket:
    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []

    async def send_json(self, message: dict[str, Any]) -> None:
        self.sent.append(message)

    def of_type(self, event_type: str) -> list[dict[str, Any]]:
        return [m for m in self.sent if m["type"] == event_type]


async def booked_via_api(
    client: AsyncClient, session: AsyncSession, position: tuple[float, float] = INSIDE
) -> tuple[dict[str, str], int]:
    await seed_zones(session)
    user = await make_user(session)
    scooter = await make_scooter(session)
    scooter.lat, scooter.lon = position
    await session.commit()
    hdrs = headers(user)
    booking = (
        await client.post("/api/bookings", json={"scooter_code": "KG-B1"}, headers=hdrs)
    ).json()
    return hdrs, booking["id"]


async def test_start_ride_returns_201_then_200_for_the_same_booking(
    client: AsyncClient, db_session: AsyncSession, clock
) -> None:
    hdrs, booking_id = await booked_via_api(client, db_session)
    listener = FakeSocket()
    hub.register(listener)  # type: ignore[arg-type]
    hub.identify(listener, int(hdrs["X-User-Id"]))  # type: ignore[arg-type]
    try:
        first = await client.post("/api/rides", json={"booking_id": booking_id}, headers=hdrs)
        again = await client.post("/api/rides", json={"booking_id": booking_id}, headers=hdrs)
    finally:
        hub.unregister(listener)  # type: ignore[arg-type]

    assert first.status_code == 201
    assert again.status_code == 200
    body = first.json()
    assert again.json()["id"] == body["id"]
    assert body["status"] == "active"
    assert body["scooter_code"] == "KG-B1"
    assert body["started_at"] == "2026-09-12T12:00:00Z"
    assert body["ride_rate_per_minute"] == str(settings.ride_rate_per_minute)
    assert body["pause_rate_per_minute"] == str(settings.pause_rate_per_minute)
    assert body["segments"] == [
        {
            "kind": "ride",
            "started_at": "2026-09-12T12:00:00Z",
            "ended_at": None,
            "seconds": None,
            "cost": None,
        }
    ]
    assert body["receipt"] is None
    assert listener.of_type("ride.started")[0]["ride"]["id"] == body["id"]
    assert listener.of_type("scooter.updated")[0]["scooter"]["status"] == "riding"
    assert len(listener.of_type("ride.started")) == 1  # the idempotent repeat does not re-announce


async def test_active_ride_endpoint(client: AsyncClient, db_session: AsyncSession, clock) -> None:
    hdrs, booking_id = await booked_via_api(client, db_session)
    assert (await client.get("/api/rides/active", headers=hdrs)).json() is None

    started = (
        await client.post("/api/rides", json={"booking_id": booking_id}, headers=hdrs)
    ).json()

    active = await client.get("/api/rides/active", headers=hdrs)
    assert active.status_code == 200
    assert active.json()["id"] == started["id"]


async def test_pause_resume_and_finish_with_receipt(
    client: AsyncClient, db_session: AsyncSession, clock
) -> None:
    hdrs, booking_id = await booked_via_api(client, db_session)
    ride_id = (
        await client.post("/api/rides", json={"booking_id": booking_id}, headers=hdrs)
    ).json()["id"]
    listener = FakeSocket()
    hub.register(listener)  # type: ignore[arg-type]
    hub.identify(listener, int(hdrs["X-User-Id"]))  # type: ignore[arg-type]
    try:
        clock.set(90)
        paused = await client.post(f"/api/rides/{ride_id}/pause", headers=hdrs)
        clock.set(150)
        resumed = await client.post(f"/api/rides/{ride_id}/resume", headers=hdrs)
        clock.set(210)
        finished = await client.post(f"/api/rides/{ride_id}/finish", headers=hdrs)
    finally:
        hub.unregister(listener)  # type: ignore[arg-type]

    assert paused.status_code == resumed.status_code == finished.status_code == 200
    assert paused.json()["status"] == "paused"
    assert paused.json()["segments"][0] == {
        "kind": "ride",
        "started_at": "2026-09-12T12:00:00Z",
        "ended_at": "2026-09-12T12:01:30Z",
        "seconds": 90,
        "cost": "7.50",
    }
    assert resumed.json()["status"] == "active"
    body = finished.json()
    assert body["status"] == "finished"
    assert body["finished_at"] == "2026-09-12T12:03:30Z"
    assert body["receipt"] == {
        "ride_seconds": 150,
        "pause_seconds": 60,
        "ride_cost": "12.50",
        "pause_cost": "1.50",
        "total_cost": "14.00",
        "currency": "KGS",
    }
    assert [s["cost"] for s in body["segments"]] == ["7.50", "1.50", "5.00"]
    assert [m["type"] for m in listener.sent if m["type"].startswith("ride.")] == [
        "ride.paused",
        "ride.resumed",
        "ride.finished",
    ]
    public = listener.of_type("scooter.updated")
    assert [s["scooter"]["paused"] for s in public[:2]] == [True, False]
    assert public[-1]["scooter"]["status"] == "available"
    db_session.expire_all()
    scooter = await db_session.scalar(select(Scooter).where(Scooter.code == "KG-B1"))
    assert scooter is not None and scooter.status is ScooterStatus.AVAILABLE


async def test_finish_outside_zone_returns_409_with_a_clear_message(
    client: AsyncClient, db_session: AsyncSession, clock
) -> None:
    hdrs, booking_id = await booked_via_api(client, db_session, position=OUTSIDE)
    ride_id = (
        await client.post("/api/rides", json={"booking_id": booking_id}, headers=hdrs)
    ).json()["id"]

    response = await client.post(f"/api/rides/{ride_id}/finish", headers=hdrs)

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["code"] == "outside_service_zone"
    assert "outside the service zone" in detail["message"]
    assert (await client.get("/api/rides/active", headers=hdrs)).json()["status"] == "active"


async def test_double_finish_is_idempotent_over_http(
    client: AsyncClient, db_session: AsyncSession, clock
) -> None:
    hdrs, booking_id = await booked_via_api(client, db_session)
    ride_id = (
        await client.post("/api/rides", json={"booking_id": booking_id}, headers=hdrs)
    ).json()["id"]
    clock.set(60)
    first = await client.post(f"/api/rides/{ride_id}/finish", headers=hdrs)
    clock.set(600)
    second = await client.post(f"/api/rides/{ride_id}/finish", headers=hdrs)

    assert first.status_code == second.status_code == 200
    assert first.json()["receipt"] == second.json()["receipt"]
    assert second.json()["receipt"]["total_cost"] == "5.00"


async def test_ride_errors_over_http(client: AsyncClient, db_session: AsyncSession, clock) -> None:
    hdrs, booking_id = await booked_via_api(client, db_session)
    other = await make_user(db_session, "Other")
    other_hdrs = headers(other)
    ride_id = (
        await client.post("/api/rides", json={"booking_id": booking_id}, headers=hdrs)
    ).json()["id"]

    assert (
        await client.post("/api/rides", json={"booking_id": 999}, headers=hdrs)
    ).status_code == 404
    assert (
        await client.post("/api/rides", json={"booking_id": booking_id}, headers=other_hdrs)
    ).status_code == 403
    assert (await client.post(f"/api/rides/{ride_id}/pause", headers=other_hdrs)).status_code == 403
    assert (await client.post(f"/api/rides/{ride_id}/pause")).status_code == 401
    assert (await client.post("/api/rides", json={}, headers=hdrs)).status_code == 422


async def test_concurrent_starts_for_one_booking_create_a_single_ride(
    client: AsyncClient, committed_db: async_sessionmaker[AsyncSession], clock
) -> None:
    async with committed_db() as session:
        await seed_zones(session)
        hdrs, booking_id = await booked_via_api(client, session)

    responses = await asyncio.gather(
        *(
            client.post("/api/rides", json={"booking_id": booking_id}, headers=hdrs)
            for _ in range(3)
        )
    )

    assert sorted(r.status_code for r in responses) == [200, 200, 201]
    assert len({r.json()["id"] for r in responses}) == 1
    async with committed_db() as session:
        rides = await session.scalar(select(func.count()).select_from(Ride))
        active = await session.scalar(
            select(func.count()).select_from(Ride).where(Ride.status == RideStatus.ACTIVE)
        )
    assert rides == active == 1
