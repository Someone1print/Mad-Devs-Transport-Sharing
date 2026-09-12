"""Receipt e-mail on finish (exactly one per ride) and the rider's ride history."""

import asyncio
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import Email
from app.realtime.hub import hub
from app.seed import seed_zones
from tests.test_bookings import headers, make_scooter, make_user
from tests.test_rides_api import FakeSocket, booked_via_api

INSIDE = (42.8756, 74.6036)


async def finished_ride(client: AsyncClient, session: AsyncSession, clock, seconds: int) -> dict:
    """Book, start, pause a bit, finish inside the zone after `seconds`; returns the finish body."""
    hdrs, booking_id = await booked_via_api(client, session)
    ride_id = (
        await client.post("/api/rides", json={"booking_id": booking_id}, headers=hdrs)
    ).json()["id"]
    clock.set(seconds - 60)
    await client.post(f"/api/rides/{ride_id}/pause", headers=hdrs)
    clock.set(seconds - 30)
    await client.post(f"/api/rides/{ride_id}/resume", headers=hdrs)
    clock.set(seconds)
    body = (await client.post(f"/api/rides/{ride_id}/finish", headers=hdrs)).json()
    body["_headers"] = hdrs
    return body


async def test_finishing_a_ride_sends_exactly_one_receipt_email(
    client: AsyncClient, db_session: AsyncSession, clock
) -> None:
    ride = await finished_ride(client, db_session, clock, seconds=150)
    hdrs = ride["_headers"]

    emails = (await client.get("/api/emails", headers=hdrs)).json()

    assert len(emails) == 1
    email = emails[0]
    assert email["subject"] == f"Чек за поездку на {ride['scooter_code']}"
    assert email["to_address"].endswith("@example.invalid")
    receipt = ride["receipt"]
    # the same money the receipt carries, verbatim
    assert f"{receipt['ride_cost']} KGS" in email["body"]
    assert f"{receipt['pause_cost']} KGS" in email["body"]
    assert f"Итого: {receipt['total_cost']} KGS" in email["body"]
    assert "Ехали: 2 мин 00 с" in email["body"]
    assert "Стояли: 0 мин 30 с" in email["body"]
    assert email["dedup_key"] == f"ride:{ride['id']}:receipt"
    # the ride window in the service's zone (API_T0 12:00 UTC is 18:00 in Bishkek), labelled
    assert "завершена (12.09.2026 18:00 — 18:02 (UTC+6))" in email["body"]


async def test_receipt_is_sent_for_a_rider_with_the_widest_64_char_name(
    client: AsyncClient, db_session: AsyncSession, clock
) -> None:
    await seed_zones(db_session)
    user = await make_user(db_session, "щ" * 64)
    scooter = await make_scooter(db_session)
    scooter.lat, scooter.lon = INSIDE
    await db_session.commit()
    hdrs = headers(user)
    booking = (
        await client.post("/api/bookings", json={"scooter_code": "KG-B1"}, headers=hdrs)
    ).json()
    ride_id = (
        await client.post("/api/rides", json={"booking_id": booking["id"]}, headers=hdrs)
    ).json()["id"]
    clock.set(60)

    finished = await client.post(f"/api/rides/{ride_id}/finish", headers=hdrs)
    emails = (await client.get("/api/emails", headers=hdrs)).json()

    assert finished.status_code == 200
    assert finished.json()["status"] == "finished"
    assert len(emails) == 1
    assert len(emails[0]["to_address"]) <= 255


async def test_double_finish_does_not_send_a_second_email(
    client: AsyncClient, db_session: AsyncSession, clock
) -> None:
    ride = await finished_ride(client, db_session, clock, seconds=120)
    hdrs = ride["_headers"]

    clock.set(600)
    again = await client.post(f"/api/rides/{ride['id']}/finish", headers=hdrs)

    assert again.status_code == 200
    assert await db_session.scalar(select(func.count()).select_from(Email)) == 1


async def test_concurrent_finishes_send_one_email(
    client: AsyncClient, committed_db: async_sessionmaker[AsyncSession], clock
) -> None:
    async with committed_db() as session:
        await seed_zones(session)
        hdrs, booking_id = await booked_via_api(client, session)
    ride_id = (
        await client.post("/api/rides", json={"booking_id": booking_id}, headers=hdrs)
    ).json()["id"]
    clock.set(90)

    responses = await asyncio.gather(
        *(client.post(f"/api/rides/{ride_id}/finish", headers=hdrs) for _ in range(4))
    )

    assert {r.status_code for r in responses} == {200}
    assert len({r.json()["receipt"]["total_cost"] for r in responses}) == 1
    async with committed_db() as session:
        assert await session.scalar(select(func.count()).select_from(Email)) == 1


async def test_receipt_email_is_announced_to_the_rider_over_the_socket(
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
        clock.set(60)
        await client.post(f"/api/rides/{ride_id}/finish", headers=hdrs)
    finally:
        hub.unregister(listener)  # type: ignore[arg-type]

    sent = listener.of_type("email.sent")
    assert len(sent) == 1
    assert sent[0]["email"]["dedup_key"] == f"ride:{ride_id}:receipt"


async def test_emails_are_private_and_newest_first(
    client: AsyncClient, db_session: AsyncSession, clock
) -> None:
    ride = await finished_ride(client, db_session, clock, seconds=100)
    hdrs = ride["_headers"]
    await make_scooter(db_session, code="KG-B2")
    booking = (
        await client.post("/api/bookings", json={"scooter_code": "KG-B2"}, headers=hdrs)
    ).json()
    later = (
        await client.post("/api/rides", json={"booking_id": booking["id"]}, headers=hdrs)
    ).json()
    clock.set(400)
    await client.post(f"/api/rides/{later['id']}/finish", headers=hdrs)
    other = await make_user(db_session, "Other")

    mine = (await client.get("/api/emails", headers=hdrs)).json()
    theirs = (await client.get("/api/emails", headers=headers(other))).json()
    anonymous = await client.get("/api/emails")

    assert [e["dedup_key"] for e in mine] == [
        f"ride:{later['id']}:receipt",
        f"ride:{ride['id']}:receipt",
    ]
    assert theirs == []
    assert anonymous.status_code == 401


async def test_ride_history_lists_finished_rides_newest_first_with_receipts(
    client: AsyncClient, db_session: AsyncSession, clock
) -> None:
    first = await finished_ride(client, db_session, clock, seconds=120)
    hdrs = first["_headers"]
    # a second ride for the same rider on another scooter
    await make_scooter(db_session, code="KG-B2")
    booking = (
        await client.post("/api/bookings", json={"scooter_code": "KG-B2"}, headers=hdrs)
    ).json()
    ride_id = (
        await client.post("/api/rides", json={"booking_id": booking["id"]}, headers=hdrs)
    ).json()["id"]
    clock.set(700)
    second = (await client.post(f"/api/rides/{ride_id}/finish", headers=hdrs)).json()

    history = (await client.get("/api/rides", headers=hdrs)).json()

    assert [r["id"] for r in history] == [second["id"], first["id"]]
    assert history[0]["status"] == history[1]["status"] == "finished"
    assert history[1]["receipt"] == first["receipt"]
    assert history[1]["receipt"]["total_cost"] == "8.25"  # ride 90 s 7.50 + pause 30 s 0.75
    assert Decimal(history[0]["receipt"]["total_cost"]) == Decimal(second["receipt"]["total_cost"])
    assert all(seg["cost"] is not None for r in history for seg in r["segments"])


async def test_ride_history_excludes_unfinished_rides_and_other_users(
    client: AsyncClient, db_session: AsyncSession, clock
) -> None:
    finished = await finished_ride(client, db_session, clock, seconds=120)
    hdrs = finished["_headers"]
    await make_scooter(db_session, code="KG-B2")
    booking = (
        await client.post("/api/bookings", json={"scooter_code": "KG-B2"}, headers=hdrs)
    ).json()
    running = (
        await client.post("/api/rides", json={"booking_id": booking["id"]}, headers=hdrs)
    ).json()
    other = await make_user(db_session, "Other")

    history = (await client.get("/api/rides", headers=hdrs)).json()
    theirs = (await client.get("/api/rides", headers=headers(other))).json()
    active = (await client.get("/api/rides/active", headers=hdrs)).json()

    assert [r["id"] for r in history] == [finished["id"]]
    assert theirs == []
    assert active["id"] == running["id"]
