"""A flat battery ends the ride by itself: bill as usual, no zone check, scooter unavailable,
receipt e-mail with the explanation, and exactly one finish however the reports race."""

import asyncio

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import settings
from app.models import Email, Ride, Scooter, ScooterStatus
from app.realtime.hub import hub
from app.seed import seed_zones
from tests.test_bookings import headers, make_user, user_id
from tests.test_rides_api import FakeSocket, booked_via_api
from tests.test_rides_service import OUTSIDE

THRESHOLD = settings.ride_auto_finish_battery  # 10 by default


def telemetry(battery: int, position: tuple[float, float] = OUTSIDE) -> dict:
    return {"code": "KG-B1", "lat": position[0], "lon": position[1], "battery": battery}


async def started_ride(client: AsyncClient, session: AsyncSession) -> tuple[dict[str, str], int]:
    """A ride started OUTSIDE the zone: the rider could not finish it by hand."""
    hdrs, booking_id = await booked_via_api(client, session, OUTSIDE)
    ride_id = (
        await client.post("/api/rides", json={"booking_id": booking_id}, headers=hdrs)
    ).json()["id"]
    return hdrs, ride_id


def listening(hdrs: dict[str, str]) -> FakeSocket:
    listener = FakeSocket()
    hub.register(listener)  # type: ignore[arg-type]
    hub.identify(listener, user_id(hdrs))  # type: ignore[arg-type]
    return listener


async def test_flat_battery_finishes_the_ride_with_a_bill_and_no_zone_check(
    client: AsyncClient, db_session: AsyncSession, clock
) -> None:
    hdrs, ride_id = await started_ride(client, db_session)
    listener = listening(hdrs)
    clock.set(90)
    try:
        response = await client.post("/api/telemetry", json=telemetry(THRESHOLD - 1))
    finally:
        hub.unregister(listener)  # type: ignore[arg-type]
    ride = (await client.get(f"/api/rides/{ride_id}", headers=hdrs)).json()
    active = (await client.get("/api/rides/active", headers=hdrs)).json()
    emails = (await client.get("/api/emails", headers=hdrs)).json()

    # the scooter: unavailable (not available), where the last report put it, with that charge
    assert response.status_code == 200
    assert response.json()["status"] == "unavailable"
    assert response.json()["battery"] == THRESHOLD - 1
    assert (response.json()["lat"], response.json()["lon"]) == OUTSIDE
    # the ride: finished outside the zone, billed up to the report, with the reason and the facts
    assert active is None
    assert ride["status"] == "finished"
    assert ride["finish_reason"] == "battery"
    assert ride["finish_battery"] == THRESHOLD - 1
    assert ride["finish_battery_threshold"] == THRESHOLD
    assert ride["receipt"] == {
        "ride_seconds": 90,
        "pause_seconds": 0,
        "ride_cost": "7.50",
        "pause_cost": "0.00",
        "total_cost": "7.50",
        "currency": "KGS",
    }
    # the e-mail: one, with the explanation, the amounts verbatim
    assert len(emails) == 1
    assert emails[0]["subject"] == "Поездка на KG-B1 завершена: самокат разрядился"
    assert f"заряд упал до {THRESHOLD - 1} %" in emails[0]["body"]
    assert f"при заряде ниже {THRESHOLD} %" in emails[0]["body"]
    assert "Итого: 7.50 KGS" in emails[0]["body"]
    # the rider is told over the socket, in order: the ride, then the letter
    finished = listener.of_type("ride.finished")
    assert len(finished) == 1 and finished[0]["ride"]["finish_reason"] == "battery"
    assert len(listener.of_type("email.sent")) == 1
    assert listener.of_type("scooter.updated")[-1]["scooter"]["status"] == "unavailable"


async def test_battery_at_the_threshold_keeps_the_ride_going(
    client: AsyncClient, db_session: AsyncSession, clock
) -> None:
    hdrs, ride_id = await started_ride(client, db_session)
    clock.set(30)

    response = await client.post("/api/telemetry", json=telemetry(THRESHOLD))
    active = (await client.get("/api/rides/active", headers=hdrs)).json()

    assert response.json()["status"] == "riding"  # strictly below ends it, equal does not
    assert active["id"] == ride_id and active["status"] == "active"


async def test_a_paused_ride_ends_on_a_flat_battery_too(
    client: AsyncClient, db_session: AsyncSession, clock
) -> None:
    hdrs, ride_id = await started_ride(client, db_session)
    clock.set(60)
    await client.post(f"/api/rides/{ride_id}/pause", headers=hdrs)
    clock.set(120)

    await client.post("/api/telemetry", json=telemetry(0))
    ride = (await client.get(f"/api/rides/{ride_id}", headers=hdrs)).json()

    assert ride["status"] == "finished" and ride["finish_reason"] == "battery"
    assert ride["receipt"]["ride_seconds"] == 60 and ride["receipt"]["pause_seconds"] == 60
    assert ride["receipt"]["total_cost"] == "6.50"  # 5.00 riding + 1.50 paused


async def test_manual_finish_after_the_auto_finish_is_idempotent(
    client: AsyncClient, db_session: AsyncSession, clock
) -> None:
    hdrs, ride_id = await started_ride(client, db_session)
    clock.set(90)
    await client.post("/api/telemetry", json=telemetry(THRESHOLD - 1))
    listener = listening(hdrs)
    clock.set(200)
    try:
        again = await client.post(f"/api/rides/{ride_id}/finish", headers=hdrs)
    finally:
        hub.unregister(listener)  # type: ignore[arg-type]

    assert again.status_code == 200
    assert again.json()["finish_reason"] == "battery"  # the rider's click changes nothing
    assert again.json()["receipt"]["ride_seconds"] == 90
    assert await db_session.scalar(select(func.count()).select_from(Email)) == 1
    assert listener.sent == []  # nothing new to announce


async def test_flat_battery_after_the_manual_finish_is_plain_telemetry(
    client: AsyncClient, db_session: AsyncSession, clock
) -> None:
    from tests.test_rides_service import INSIDE

    hdrs, booking_id = await booked_via_api(client, db_session, INSIDE)
    ride_id = (
        await client.post("/api/rides", json={"booking_id": booking_id}, headers=hdrs)
    ).json()["id"]
    clock.set(60)
    finished = (await client.post(f"/api/rides/{ride_id}/finish", headers=hdrs)).json()

    response = await client.post("/api/telemetry", json=telemetry(THRESHOLD - 1, INSIDE))
    ride = (await client.get(f"/api/rides/{ride_id}", headers=hdrs)).json()

    assert finished["finish_reason"] == "user"
    assert ride["finish_reason"] == "user" and ride["finished_at"] == finished["finished_at"]
    # the low-battery rule for a free scooter, not a second finish
    assert response.json()["status"] == "unavailable"
    assert await db_session.scalar(select(func.count()).select_from(Email)) == 1


@pytest.mark.parametrize("first", ["finish", "telemetry"])
async def test_telemetry_and_manual_finish_racing_on_the_ride_lock_finish_it_once(
    client: AsyncClient, committed_db: async_sessionmaker[AsyncSession], clock, first: str
) -> None:
    """Both requests wait on the ride row a third session holds; released together, one wins.

    PostgreSQL hands a contended row lock to waiters in arrival order, so `first` decides the
    winner: the rider's finish (reason `user`, then plain telemetry) or the flat report
    (reason `battery`, then an idempotent finish).
    """
    from tests.test_rides_service import INSIDE

    async with committed_db() as session:
        await seed_zones(session)
        hdrs, booking_id = await booked_via_api(client, session, INSIDE)
    ride_id = (
        await client.post("/api/rides", json={"booking_id": booking_id}, headers=hdrs)
    ).json()["id"]
    listener = listening(hdrs)
    clock.set(90)
    try:
        async with committed_db() as locker:
            await locker.execute(
                text("SELECT id FROM rides WHERE id = :id FOR UPDATE"), {"id": ride_id}
            )
            post_finish = lambda: client.post(f"/api/rides/{ride_id}/finish", headers=hdrs)  # noqa: E731
            post_flat = lambda: client.post("/api/telemetry", json=telemetry(THRESHOLD - 1, INSIDE))  # noqa: E731
            if first == "finish":
                manual = asyncio.create_task(post_finish())
                await asyncio.sleep(0.1)  # let it reach the lock queue first
                flat = asyncio.create_task(post_flat())
            else:
                flat = asyncio.create_task(post_flat())
                await asyncio.sleep(0.1)
                manual = asyncio.create_task(post_finish())
            await asyncio.sleep(0.3)
            assert not manual.done() and not flat.done(), "both must wait for the ride row"
            await locker.commit()
            finish_response, telemetry_response = await asyncio.wait_for(
                asyncio.gather(manual, flat), timeout=5
            )
    finally:
        hub.unregister(listener)  # type: ignore[arg-type]

    assert finish_response.status_code == 200 and telemetry_response.status_code == 200
    async with committed_db() as session:
        ride = await session.get(Ride, ride_id)
        scooter = await session.scalar(select(Scooter).where(Scooter.code == "KG-B1"))
        emails = await session.scalar(select(func.count()).select_from(Email))
    assert ride is not None and ride.status.value == "finished"
    assert ride.finish_reason is not None
    assert ride.ride_seconds == 90  # one closing time, whoever won
    assert emails == 1
    assert len(listener.of_type("ride.finished")) == 1
    assert len(listener.of_type("email.sent")) == 1
    # whoever won, a scooter reporting a flat battery is unavailable afterwards
    assert scooter is not None and scooter.status is ScooterStatus.UNAVAILABLE
    assert finish_response.json()["finish_reason"] == ride.finish_reason.value
    assert ride.finish_reason.value == ("user" if first == "finish" else "battery")


async def test_get_ride_is_private(client: AsyncClient, db_session: AsyncSession, clock) -> None:
    hdrs, ride_id = await started_ride(client, db_session)
    other = await make_user(db_session, "Other")

    mine = await client.get(f"/api/rides/{ride_id}", headers=hdrs)
    theirs = await client.get(f"/api/rides/{ride_id}", headers=headers(other))
    unknown = await client.get("/api/rides/999999", headers=hdrs)

    assert mine.status_code == 200 and mine.json()["id"] == ride_id
    assert theirs.status_code == 403
    assert unknown.status_code == 404


async def test_the_ride_survives_the_client_and_is_billed_for_the_whole_time(
    client: AsyncClient, db_session: AsyncSession, clock
) -> None:
    """The client may vanish (tab closed): the server keeps the ride and the meter running."""
    from tests.test_rides_service import INSIDE

    hdrs, booking_id = await booked_via_api(client, db_session, INSIDE)
    started = (
        await client.post("/api/rides", json={"booking_id": booking_id}, headers=hdrs)
    ).json()

    clock.set(90)  # nothing from the client for a minute and a half
    restored = (await client.get("/api/rides/active", headers=hdrs)).json()
    clock.set(120)
    finished = (await client.post(f"/api/rides/{started['id']}/finish", headers=hdrs)).json()

    # what a reopened tab gets: the same ride, its start time, one open segment to count from
    assert restored["id"] == started["id"] and restored["status"] == "active"
    assert restored["started_at"] == started["started_at"]
    assert [s["ended_at"] for s in restored["segments"]] == [None]
    assert (
        finished["receipt"]["ride_seconds"] == 120 and finished["receipt"]["total_cost"] == "10.00"
    )
