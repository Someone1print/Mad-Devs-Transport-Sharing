"""Ride state machine and billing integration, driven with explicit timestamps (no waiting)."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.billing import SegmentKind
from app.models import Booking, BookingStatus, Ride, RideStatus, Scooter, ScooterStatus
from app.services import rides as ride_service
from app.services.bookings import create_booking
from app.services.rides import (
    RideConflictError,
    RideForbiddenError,
    RideNotFoundError,
    Tariff,
)
from app.zones import BISHKEK_CENTER_ZONE
from tests.test_bookings import make_scooter, make_user

T0 = datetime(2026, 9, 12, 10, 0, 0, tzinfo=UTC)
TARIFF = Tariff(ride_rate_per_minute=Decimal("5.00"), pause_rate_per_minute=Decimal("1.50"))
ZONE = list(BISHKEK_CENTER_ZONE.points)
INSIDE = (42.8756, 74.6036)  # Ala-Too Square
OUTSIDE = (42.8500, 74.6000)  # south of the railway
THRESHOLD = 15


def at(seconds: int) -> datetime:
    return T0 + timedelta(seconds=seconds)


async def booked(
    session: AsyncSession, name: str = "Rider", code: str = "KG-B1", battery: int = 80
) -> tuple[int, int, int]:
    """A user holding an active booking; returns (user_id, scooter_id, booking_id)."""
    user = await make_user(session, name)
    scooter = await make_scooter(session, code=code)
    scooter.battery = battery
    await session.commit()
    user_id, scooter_id = user.id, scooter.id
    booking = await create_booking(session, user_id, code, ttl=timedelta(minutes=15), now=T0)
    return user_id, scooter_id, booking.id


async def place(session: AsyncSession, scooter_id: int, position: tuple[float, float]) -> None:
    scooter = await session.get(Scooter, scooter_id)
    assert scooter is not None
    scooter.lat, scooter.lon = position
    await session.commit()


# --- start ---


async def test_start_converts_booking_and_marks_scooter_riding(db_session: AsyncSession) -> None:
    user_id, scooter_id, booking_id = await booked(db_session)

    ride, created = await ride_service.start_ride(db_session, user_id, booking_id, TARIFF, at(0))

    assert created is True
    assert ride.status is RideStatus.ACTIVE
    assert ride.started_at == at(0)
    assert ride.ride_rate_per_minute == Decimal("5.00")
    assert [(s.kind, s.ended_at) for s in ride.segments] == [(SegmentKind.RIDE, None)]
    db_session.expire_all()
    booking = await db_session.get(Booking, booking_id)
    scooter = await db_session.get(Scooter, scooter_id)
    assert booking is not None and booking.status is BookingStatus.USED
    assert scooter is not None and scooter.status is ScooterStatus.RIDING


async def test_double_start_returns_the_same_ride(db_session: AsyncSession) -> None:
    user_id, _, booking_id = await booked(db_session)
    first, _ = await ride_service.start_ride(db_session, user_id, booking_id, TARIFF, at(0))
    first_id = first.id

    again, created = await ride_service.start_ride(db_session, user_id, booking_id, TARIFF, at(5))

    assert created is False
    assert again.id == first_id
    assert len(again.segments) == 1
    assert await db_session.scalar(select(Ride).where(Ride.booking_id == booking_id)) is not None


async def test_start_rejects_other_users_booking(db_session: AsyncSession) -> None:
    _, _, booking_id = await booked(db_session)
    intruder = await make_user(db_session, "Intruder")

    with pytest.raises(RideForbiddenError):
        await ride_service.start_ride(db_session, intruder.id, booking_id, TARIFF, at(0))


@pytest.mark.parametrize("status", [BookingStatus.EXPIRED, BookingStatus.CANCELLED])
async def test_start_rejects_booking_that_is_not_active(
    db_session: AsyncSession, status: BookingStatus
) -> None:
    user_id, _, booking_id = await booked(db_session)
    booking = await db_session.get(Booking, booking_id)
    assert booking is not None
    booking.status = status
    await db_session.commit()

    with pytest.raises(RideConflictError) as exc:
        await ride_service.start_ride(db_session, user_id, booking_id, TARIFF, at(0))

    assert exc.value.code == "booking_not_active"


async def test_start_rejects_unknown_booking(db_session: AsyncSession) -> None:
    user = await make_user(db_session)

    with pytest.raises(RideNotFoundError):
        await ride_service.start_ride(db_session, user.id, 999_999, TARIFF, at(0))


async def test_start_rejects_scooter_that_became_unavailable(db_session: AsyncSession) -> None:
    user_id, scooter_id, booking_id = await booked(db_session)
    scooter = await db_session.get(Scooter, scooter_id)
    assert scooter is not None
    scooter.status = ScooterStatus.UNAVAILABLE  # telemetry reported a flat battery meanwhile
    await db_session.commit()

    with pytest.raises(RideConflictError) as exc:
        await ride_service.start_ride(db_session, user_id, booking_id, TARIFF, at(0))

    assert exc.value.code == "scooter_not_available"


async def test_booking_is_refused_while_a_ride_is_active(db_session: AsyncSession) -> None:
    user_id, _, booking_id = await booked(db_session)
    await make_scooter(db_session, code="KG-B2")
    await ride_service.start_ride(db_session, user_id, booking_id, TARIFF, at(0))

    from app.services.bookings import BookingConflictError

    with pytest.raises(BookingConflictError) as exc:
        await create_booking(db_session, user_id, "KG-B2", ttl=timedelta(minutes=15), now=at(1))

    assert exc.value.code == "user_has_active_ride"


# --- pause / resume ---


async def test_pause_closes_ride_segment_and_opens_pause_segment(db_session: AsyncSession) -> None:
    user_id, _, booking_id = await booked(db_session)
    ride, _ = await ride_service.start_ride(db_session, user_id, booking_id, TARIFF, at(0))
    ride_id = ride.id

    paused = await ride_service.pause_ride(db_session, user_id, ride_id, at(61))

    assert paused.status is RideStatus.PAUSED
    segments = [(s.kind, s.seconds, s.cost, s.ended_at) for s in paused.segments]
    assert segments == [
        (SegmentKind.RIDE, 61, Decimal("5.08"), at(61)),
        (SegmentKind.PAUSE, None, None, None),
    ]


async def test_double_pause_and_double_resume_are_idempotent(db_session: AsyncSession) -> None:
    user_id, _, booking_id = await booked(db_session)
    ride, _ = await ride_service.start_ride(db_session, user_id, booking_id, TARIFF, at(0))
    ride_id = ride.id
    await ride_service.pause_ride(db_session, user_id, ride_id, at(60))

    twice = await ride_service.pause_ride(db_session, user_id, ride_id, at(70))
    assert twice.status is RideStatus.PAUSED
    assert len(twice.segments) == 2  # no new segment for the repeated pause

    resumed = await ride_service.resume_ride(db_session, user_id, ride_id, at(90))
    again = await ride_service.resume_ride(db_session, user_id, ride_id, at(95))

    assert resumed.status is again.status is RideStatus.ACTIVE
    assert len(again.segments) == 3
    assert [s.kind for s in again.segments] == [
        SegmentKind.RIDE,
        SegmentKind.PAUSE,
        SegmentKind.RIDE,
    ]
    assert again.segments[1].seconds == 30
    assert again.segments[1].cost == Decimal("0.75")


async def test_pause_by_another_user_is_forbidden(db_session: AsyncSession) -> None:
    user_id, _, booking_id = await booked(db_session)
    other_id = (await make_user(db_session, "Other")).id
    ride, _ = await ride_service.start_ride(db_session, user_id, booking_id, TARIFF, at(0))

    with pytest.raises(RideForbiddenError):
        await ride_service.pause_ride(db_session, other_id, ride.id, at(10))


# --- finish ---


async def test_finish_inside_zone_bills_segments_and_frees_scooter(
    db_session: AsyncSession,
) -> None:
    user_id, scooter_id, booking_id = await booked(db_session)
    await place(db_session, scooter_id, INSIDE)
    ride, _ = await ride_service.start_ride(db_session, user_id, booking_id, TARIFF, at(0))
    ride_id = ride.id
    await ride_service.pause_ride(db_session, user_id, ride_id, at(90))  # ride 90 s → 7.50
    await ride_service.resume_ride(db_session, user_id, ride_id, at(150))  # pause 60 s → 1.50
    await ride_service.pause_ride(db_session, user_id, ride_id, at(211))  # ride 61 s → 5.08
    await ride_service.resume_ride(db_session, user_id, ride_id, at(212))  # pause 1 s → 0.03

    finished, done_now = await ride_service.finish_ride(
        db_session,
        user_id,
        ride_id,
        ZONE,
        THRESHOLD,
        at(213),  # ride 1 s → 0.08
    )

    assert done_now is True
    assert finished.status is RideStatus.FINISHED
    assert finished.finished_at == at(213)
    assert finished.ride_seconds == 152 and finished.pause_seconds == 61
    assert finished.ride_cost == Decimal("12.66")
    assert finished.pause_cost == Decimal("1.53")
    assert finished.total_cost == Decimal("14.19")
    assert sum((s.cost for s in finished.segments), Decimal("0")) == finished.total_cost
    assert all(s.ended_at is not None for s in finished.segments)
    db_session.expire_all()
    scooter = await db_session.get(Scooter, scooter_id)
    assert scooter is not None and scooter.status is ScooterStatus.AVAILABLE


async def test_finish_outside_zone_is_refused_and_ride_goes_on(db_session: AsyncSession) -> None:
    user_id, scooter_id, booking_id = await booked(db_session)
    await place(db_session, scooter_id, OUTSIDE)
    ride, _ = await ride_service.start_ride(db_session, user_id, booking_id, TARIFF, at(0))
    ride_id = ride.id

    with pytest.raises(RideConflictError) as exc:
        await ride_service.finish_ride(db_session, user_id, ride_id, ZONE, THRESHOLD, at(120))

    assert exc.value.code == "outside_service_zone"
    db_session.expire_all()
    stored = await db_session.get(Ride, ride_id)
    scooter = await db_session.get(Scooter, scooter_id)
    assert stored is not None and stored.status is RideStatus.ACTIVE
    assert stored.segments[-1].ended_at is None
    assert scooter is not None and scooter.status is ScooterStatus.RIDING


async def test_finish_while_paused_bills_the_open_pause(db_session: AsyncSession) -> None:
    user_id, scooter_id, booking_id = await booked(db_session)
    await place(db_session, scooter_id, INSIDE)
    ride, _ = await ride_service.start_ride(db_session, user_id, booking_id, TARIFF, at(0))
    ride_id = ride.id
    await ride_service.pause_ride(db_session, user_id, ride_id, at(60))

    finished, _ = await ride_service.finish_ride(
        db_session, user_id, ride_id, ZONE, THRESHOLD, at(120)
    )

    assert finished.pause_seconds == 60 and finished.pause_cost == Decimal("1.50")
    assert finished.total_cost == Decimal("6.50")


async def test_double_finish_returns_the_same_receipt(db_session: AsyncSession) -> None:
    user_id, scooter_id, booking_id = await booked(db_session)
    await place(db_session, scooter_id, INSIDE)
    ride, _ = await ride_service.start_ride(db_session, user_id, booking_id, TARIFF, at(0))
    ride_id = ride.id
    first, _ = await ride_service.finish_ride(db_session, user_id, ride_id, ZONE, THRESHOLD, at(90))

    again, done_now = await ride_service.finish_ride(
        db_session, user_id, ride_id, ZONE, THRESHOLD, at(500)
    )

    assert done_now is False
    assert again.total_cost == first.total_cost == Decimal("7.50")
    assert again.finished_at == at(90)
    assert len(again.segments) == 1


async def test_pause_and_resume_on_a_finished_ride_are_refused(db_session: AsyncSession) -> None:
    user_id, scooter_id, booking_id = await booked(db_session)
    await place(db_session, scooter_id, INSIDE)
    ride, _ = await ride_service.start_ride(db_session, user_id, booking_id, TARIFF, at(0))
    ride_id = ride.id
    await ride_service.finish_ride(db_session, user_id, ride_id, ZONE, THRESHOLD, at(60))

    for action in (ride_service.pause_ride, ride_service.resume_ride):
        with pytest.raises(RideConflictError) as exc:
            await action(db_session, user_id, ride_id, at(70))
        assert exc.value.code == "ride_finished"


async def test_finish_keeps_a_flat_scooter_unavailable(db_session: AsyncSession) -> None:
    user_id, scooter_id, booking_id = await booked(db_session)
    await place(db_session, scooter_id, INSIDE)
    ride, _ = await ride_service.start_ride(db_session, user_id, booking_id, TARIFF, at(0))
    scooter = await db_session.get(Scooter, scooter_id)
    assert scooter is not None
    scooter.battery = 10  # drained during the ride
    await db_session.commit()

    await ride_service.finish_ride(db_session, user_id, ride.id, ZONE, THRESHOLD, at(60))

    db_session.expire_all()
    scooter = await db_session.get(Scooter, scooter_id)
    assert scooter is not None and scooter.status is ScooterStatus.UNAVAILABLE


async def test_finish_without_any_zone_is_refused(db_session: AsyncSession) -> None:
    user_id, scooter_id, booking_id = await booked(db_session)
    await place(db_session, scooter_id, INSIDE)
    ride, _ = await ride_service.start_ride(db_session, user_id, booking_id, TARIFF, at(0))

    with pytest.raises(RideConflictError) as exc:
        await ride_service.finish_ride(db_session, user_id, ride.id, [], THRESHOLD, at(60))

    assert exc.value.code == "outside_service_zone"
