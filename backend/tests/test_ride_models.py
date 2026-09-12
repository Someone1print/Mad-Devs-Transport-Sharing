from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Booking,
    BookingStatus,
    Ride,
    RideSegment,
    RideStatus,
    SegmentKind,
    ServiceZone,
)
from tests.test_bookings import make_scooter, make_user

NOW = datetime(2026, 9, 12, 10, 0, 0, tzinfo=UTC)


async def make_ride(session: AsyncSession, user_id: int, scooter_id: int, booking_id: int) -> Ride:
    ride = Ride(
        user_id=user_id,
        scooter_id=scooter_id,
        booking_id=booking_id,
        started_at=NOW,
        ride_rate_per_minute=Decimal("5.00"),
        pause_rate_per_minute=Decimal("1.50"),
    )
    session.add(ride)
    await session.commit()
    return ride


async def make_used_booking(session: AsyncSession, user_id: int, scooter_id: int) -> Booking:
    booking = Booking(
        user_id=user_id,
        scooter_id=scooter_id,
        expires_at=NOW + timedelta(minutes=15),
        status=BookingStatus.USED,
    )
    session.add(booking)
    await session.commit()
    return booking


async def test_ride_round_trip_with_segments_keeps_decimal_money(db_session: AsyncSession) -> None:
    user = await make_user(db_session)
    scooter = await make_scooter(db_session)
    booking = await make_used_booking(db_session, user.id, scooter.id)
    ride = await make_ride(db_session, user.id, scooter.id, booking.id)
    ride_id = ride.id
    db_session.add_all(
        [
            RideSegment(
                ride_id=ride_id,
                kind=SegmentKind.RIDE,
                started_at=NOW,
                ended_at=NOW + timedelta(seconds=61),
                seconds=61,
                cost=Decimal("5.08"),
            ),
            RideSegment(
                ride_id=ride_id, kind=SegmentKind.PAUSE, started_at=NOW + timedelta(seconds=61)
            ),
        ]
    )
    await db_session.commit()
    db_session.expire_all()

    stored = await db_session.get(Ride, ride_id)

    assert stored is not None
    assert stored.status is RideStatus.ACTIVE
    assert stored.ride_rate_per_minute == Decimal("5.00")
    assert isinstance(stored.ride_rate_per_minute, Decimal)
    assert stored.total_cost is None
    kinds = [(s.kind, s.seconds, s.cost) for s in stored.segments]
    assert kinds == [
        (SegmentKind.RIDE, 61, Decimal("5.08")),
        (SegmentKind.PAUSE, None, None),
    ]
    assert isinstance(stored.segments[0].cost, Decimal)


async def test_only_one_unfinished_ride_per_user_and_per_scooter(db_session: AsyncSession) -> None:
    user_a = await make_user(db_session, "A")
    user_b = await make_user(db_session, "B")
    scooter_1 = await make_scooter(db_session, code="KG-R1")
    scooter_2 = await make_scooter(db_session, code="KG-R2")
    ids = (user_a.id, user_b.id, scooter_1.id, scooter_2.id)
    b1 = await make_used_booking(db_session, ids[0], ids[2])
    b2 = await make_used_booking(db_session, ids[0], ids[3])
    b3 = await make_used_booking(db_session, ids[1], ids[2])
    b1_id, b2_id, b3_id = b1.id, b2.id, b3.id
    await make_ride(db_session, ids[0], ids[2], b1_id)

    db_session.add(
        Ride(
            user_id=ids[0],
            scooter_id=ids[3],
            booking_id=b2_id,
            started_at=NOW,
            ride_rate_per_minute=Decimal("5.00"),
            pause_rate_per_minute=Decimal("1.50"),
        )
    )
    with pytest.raises(IntegrityError, match="uq_rides_unfinished_user"):
        await db_session.commit()
    await db_session.rollback()

    db_session.add(
        Ride(
            user_id=ids[1],
            scooter_id=ids[2],
            booking_id=b3_id,
            started_at=NOW,
            ride_rate_per_minute=Decimal("5.00"),
            pause_rate_per_minute=Decimal("1.50"),
        )
    )
    with pytest.raises(IntegrityError, match="uq_rides_unfinished_scooter"):
        await db_session.commit()
    await db_session.rollback()


async def test_one_booking_makes_at_most_one_ride(db_session: AsyncSession) -> None:
    user = await make_user(db_session)
    scooter = await make_scooter(db_session)
    booking = await make_used_booking(db_session, user.id, scooter.id)
    user_id, scooter_id, booking_id = user.id, scooter.id, booking.id
    first = await make_ride(db_session, user_id, scooter_id, booking_id)
    first.status = RideStatus.FINISHED
    await db_session.commit()

    db_session.add(
        Ride(
            user_id=user_id,
            scooter_id=scooter_id,
            booking_id=booking_id,
            started_at=NOW,
            ride_rate_per_minute=Decimal("5.00"),
            pause_rate_per_minute=Decimal("1.50"),
        )
    )
    with pytest.raises(IntegrityError, match="uq_rides_booking_id"):
        await db_session.commit()
    await db_session.rollback()


async def test_service_zone_round_trip(db_session: AsyncSession) -> None:
    db_session.add(
        ServiceZone(name="Тест", points=[{"lat": 42.87, "lon": 74.59}, {"lat": 42.88, "lon": 74.6}])
    )
    await db_session.commit()
    db_session.expire_all()

    stored = await db_session.scalar(select(ServiceZone).where(ServiceZone.name == "Тест"))

    assert stored is not None
    assert stored.points == [{"lat": 42.87, "lon": 74.59}, {"lat": 42.88, "lon": 74.6}]
    assert stored.as_points()[0].lat == 42.87


async def test_booking_status_used_is_accepted_by_the_database(db_session: AsyncSession) -> None:
    user = await make_user(db_session)
    scooter = await make_scooter(db_session)

    booking = await make_used_booking(db_session, user.id, scooter.id)
    booking_id = booking.id

    db_session.expire_all()
    stored = await db_session.get(Booking, booking_id)
    assert stored is not None and stored.status is BookingStatus.USED
