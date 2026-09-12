"""Regression tests for the holes found by the day-4 design review (see DEVLOG)."""

import asyncio
from datetime import timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.models import Booking, BookingStatus, Ride, RideStatus, Scooter, ScooterStatus
from app.services import rides as ride_service
from app.services.bookings import create_booking
from app.services.rides import RideConflictError
from app.services.scooters import status_after_telemetry
from tests.test_bookings import make_scooter, make_user
from tests.test_rides_service import INSIDE, T0, TARIFF, ZONES, at, booked, place

THRESHOLD = 15


# --- 1. a scooter in a ride keeps `riding` whatever the battery says ---


@pytest.mark.parametrize("battery", [0, 14, 15, 90])
def test_riding_is_sticky_against_telemetry(battery: int) -> None:
    assert status_after_telemetry(ScooterStatus.RIDING, battery, THRESHOLD) is ScooterStatus.RIDING


async def test_low_battery_telemetry_during_a_ride_keeps_the_scooter_riding(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user_id, scooter_id, booking_id = await booked(db_session)
    await ride_service.start_ride(db_session, user_id, booking_id, TARIFF, at(0))

    response = await client.post(
        "/api/telemetry", json={"code": "KG-B1", "lat": 42.87, "lon": 74.59, "battery": 5}
    )

    assert response.status_code == 200
    assert response.json()["status"] == "riding"
    assert response.json()["battery"] == 5
    db_session.expire_all()
    scooter = await db_session.get(Scooter, scooter_id)
    assert scooter is not None and scooter.status is ScooterStatus.RIDING


# --- 2. telemetry serialises with ride transitions on the scooter row ---


async def test_telemetry_waiting_on_the_row_lock_sees_the_committed_status(
    client: AsyncClient, committed_db: async_sessionmaker[AsyncSession]
) -> None:
    """A finish that commits `available` while telemetry waits must not be overwritten."""
    async with committed_db() as session:
        scooter = await make_scooter(session, status=ScooterStatus.RIDING)
        scooter_id = scooter.id

    async with committed_db() as locker:
        await locker.execute(
            text("SELECT id FROM scooters WHERE id = :id FOR UPDATE"), {"id": scooter_id}
        )
        request = asyncio.create_task(
            client.post(
                "/api/telemetry", json={"code": "KG-B1", "lat": 42.87, "lon": 74.59, "battery": 80}
            )
        )
        await asyncio.sleep(0.3)
        assert not request.done(), "telemetry must wait while the row is locked"
        await locker.execute(
            text("UPDATE scooters SET status = 'available' WHERE id = :id"), {"id": scooter_id}
        )
        await locker.commit()
        response = await asyncio.wait_for(request, timeout=5)

    assert response.status_code == 200
    assert response.json()["status"] == "available"
    async with committed_db() as session:
        stored = await session.get(Scooter, scooter_id)
    assert stored is not None and stored.status is ScooterStatus.AVAILABLE


# --- 3. `now` is clamped after the lock: a reordered request bills a zero segment, not a 500 ---


async def test_pause_with_a_clock_earlier_than_the_open_segment_bills_zero_seconds(
    db_session: AsyncSession,
) -> None:
    user_id, _, booking_id = await booked(db_session)
    ride, _ = await ride_service.start_ride(db_session, user_id, booking_id, TARIFF, at(10))
    ride_id = ride.id

    paused = await ride_service.pause_ride(db_session, user_id, ride_id, at(5))

    assert paused.status is RideStatus.PAUSED
    assert paused.segments[0].seconds == 0 and paused.segments[0].cost == Decimal("0.00")
    assert paused.segments[0].ended_at == at(10)  # clamped to the segment start
    assert paused.segments[1].started_at == at(10)


async def test_finish_with_an_earlier_clock_is_clamped_too(db_session: AsyncSession) -> None:
    user_id, scooter_id, booking_id = await booked(db_session)
    await place(db_session, scooter_id, INSIDE)
    ride, _ = await ride_service.start_ride(db_session, user_id, booking_id, TARIFF, at(60))

    finished, _ = await ride_service.finish_ride(
        db_session, user_id, ride.id, ZONES, THRESHOLD, at(0)
    )

    assert finished.finished_at == at(60)
    assert finished.total_cost == Decimal("0.00")


# --- 4. start refuses a booking that is past its deadline even before the sweeper ran ---


async def test_start_refuses_an_expired_but_unswept_booking(db_session: AsyncSession) -> None:
    user_id, _, booking_id = await booked(db_session)  # expires at T0 + 15 min

    with pytest.raises(RideConflictError) as exc:
        await ride_service.start_ride(
            db_session, user_id, booking_id, TARIFF, T0 + timedelta(minutes=15, seconds=1)
        )

    assert exc.value.code == "booking_not_active"
    booking = await db_session.get(Booking, booking_id)
    assert booking is not None and booking.status is BookingStatus.ACTIVE  # the sweeper's job


# --- 5. `paused` is a real column: pause/resume bump updated_at so clients never see it stale ---


async def test_pause_and_resume_bump_the_scooter_updated_at(db_session: AsyncSession) -> None:
    user_id, scooter_id, booking_id = await booked(db_session)
    ride, _ = await ride_service.start_ride(db_session, user_id, booking_id, TARIFF, at(0))
    ride_id = ride.id
    before = (await db_session.get(Scooter, scooter_id)).updated_at  # type: ignore[union-attr]

    await ride_service.pause_ride(db_session, user_id, ride_id, at(30))
    db_session.expire_all()
    paused = await db_session.get(Scooter, scooter_id)
    assert paused is not None and paused.paused is True and paused.updated_at > before
    paused_at = paused.updated_at  # the identity map returns the same object below

    await ride_service.resume_ride(db_session, user_id, ride_id, at(60))
    db_session.expire_all()
    resumed = await db_session.get(Scooter, scooter_id)
    assert resumed is not None and resumed.paused is False and resumed.updated_at > paused_at


# --- 6. an idempotent second finish never touches a scooter someone else holds ---


async def test_second_finish_does_not_clobber_the_next_users_booking(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user_id, scooter_id, booking_id = await booked(db_session)
    await place(db_session, scooter_id, INSIDE)
    ride, _ = await ride_service.start_ride(db_session, user_id, booking_id, TARIFF, at(0))
    ride_id = ride.id
    await ride_service.finish_ride(db_session, user_id, ride_id, ZONES, THRESHOLD, at(60))
    next_user = await make_user(db_session, "Next")
    next_id = next_user.id
    await create_booking(db_session, next_id, "KG-B1", ttl=timedelta(minutes=15), now=at(61))

    _again, finished_now = await ride_service.finish_ride(
        db_session, user_id, ride_id, ZONES, THRESHOLD, at(120)
    )

    assert finished_now is False
    db_session.expire_all()
    scooter = await db_session.get(Scooter, scooter_id)
    assert scooter is not None and scooter.status is ScooterStatus.RESERVED
    assert (await db_session.get(Ride, ride_id)).finished_at == at(60)  # type: ignore[union-attr]


# --- 7. the receipt columns can only hold a consistent breakdown ---


async def test_database_refuses_an_inconsistent_receipt(db_session: AsyncSession) -> None:
    from sqlalchemy.exc import IntegrityError

    user_id, scooter_id, booking_id = await booked(db_session)
    await place(db_session, scooter_id, INSIDE)
    ride, _ = await ride_service.start_ride(db_session, user_id, booking_id, TARIFF, at(0))
    ride_id = ride.id
    await ride_service.finish_ride(db_session, user_id, ride_id, ZONES, THRESHOLD, at(60))

    with pytest.raises(IntegrityError, match="ck_rides_receipt_adds_up"):
        await db_session.execute(
            text("UPDATE rides SET total_cost = total_cost + 0.01 WHERE id = :id"), {"id": ride_id}
        )
    await db_session.rollback()


async def test_stored_receipt_equals_the_sum_of_stored_segment_costs(
    db_session: AsyncSession,
) -> None:
    user_id, scooter_id, booking_id = await booked(db_session)
    await place(db_session, scooter_id, INSIDE)
    ride, _ = await ride_service.start_ride(db_session, user_id, booking_id, TARIFF, at(0))
    ride_id = ride.id
    await ride_service.pause_ride(db_session, user_id, ride_id, at(61))
    await ride_service.resume_ride(db_session, user_id, ride_id, at(62))
    await ride_service.finish_ride(db_session, user_id, ride_id, ZONES, THRESHOLD, at(63))

    sums = (
        await db_session.execute(
            text(
                "SELECT SUM(cost) FILTER (WHERE kind = 'ride'), "
                "SUM(cost) FILTER (WHERE kind = 'pause'), SUM(cost) "
                "FROM ride_segments WHERE ride_id = :id"
            ),
            {"id": ride_id},
        )
    ).one()
    stored = await db_session.get(Ride, ride_id)
    assert stored is not None
    assert (stored.ride_cost, stored.pause_cost, stored.total_cost) == tuple(sums)
    assert stored.total_cost == Decimal("5.19")  # ride 61 s 5.08 + pause 1 s 0.03 + ride 1 s 0.08


# --- 8. settings refuse tariffs that the NUMERIC(8,2) snapshot could not store exactly ---


@pytest.mark.parametrize("value", ["5.005", "1e7", "-1"])
def test_tariff_settings_reject_unstorable_values(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv("RIDE_RATE_PER_MINUTE", value)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


# --- 9. server error text stays English; the client owns the Russian wording ---


async def test_outside_zone_message_is_english_like_every_other_api_error(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    from app.seed import seed_zones

    await seed_zones(db_session)
    user_id, scooter_id, booking_id = await booked(db_session)
    await place(db_session, scooter_id, (42.8500, 74.6000))
    ride, _ = await ride_service.start_ride(db_session, user_id, booking_id, TARIFF, at(0))
    user = await db_session.get(Booking, booking_id)
    assert user is not None

    response = await client.post(
        f"/api/rides/{ride.id}/finish", headers={"X-User-Id": str(user_id)}
    )

    assert response.status_code == 409
    assert response.json()["detail"] == {
        "code": "outside_service_zone",
        "message": "The scooter is outside the service zone; return inside it to finish the ride",
    }


# --- 10. sub-second toggling cannot zero the bill: segment seconds carry the remainder ---


async def test_rapid_pause_resume_toggling_still_bills_the_whole_ride(
    db_session: AsyncSession,
) -> None:
    from datetime import timedelta as td

    user_id, scooter_id, booking_id = await booked(db_session)
    await place(db_session, scooter_id, INSIDE)
    ride, _ = await ride_service.start_ride(db_session, user_id, booking_id, TARIFF, at(0))
    ride_id = ride.id
    t = T0
    for i in range(20):  # a toggle every 0.9 s: every segment is shorter than a second
        t += td(milliseconds=900)
        action = ride_service.pause_ride if i % 2 == 0 else ride_service.resume_ride
        await action(db_session, user_id, ride_id, t)
    t += td(milliseconds=900)  # 18.9 s in total

    finished, _ = await ride_service.finish_ride(db_session, user_id, ride_id, ZONES, THRESHOLD, t)

    assert finished.ride_seconds + finished.pause_seconds == 18  # floor(18.9), not 0
    assert finished.total_cost > Decimal("0.00")
    assert sum(s.seconds or 0 for s in finished.segments) == 18
    # per segment, seconds are the whole seconds elapsed since the ride start, differenced
    assert all(s.seconds in (0, 1) for s in finished.segments)


async def test_segment_seconds_sum_to_the_whole_ride_duration(db_session: AsyncSession) -> None:
    from datetime import timedelta as td

    user_id, scooter_id, booking_id = await booked(db_session)
    await place(db_session, scooter_id, INSIDE)
    ride, _ = await ride_service.start_ride(db_session, user_id, booking_id, TARIFF, at(0))
    ride_id = ride.id
    await ride_service.pause_ride(
        db_session, user_id, ride_id, T0 + td(seconds=10, milliseconds=600)
    )
    await ride_service.resume_ride(
        db_session, user_id, ride_id, T0 + td(seconds=20, milliseconds=700)
    )

    finished, _ = await ride_service.finish_ride(
        db_session, user_id, ride_id, ZONES, THRESHOLD, T0 + td(seconds=30, milliseconds=900)
    )

    assert [s.seconds for s in finished.segments] == [10, 10, 10]
    assert finished.ride_seconds == 20 and finished.pause_seconds == 10
