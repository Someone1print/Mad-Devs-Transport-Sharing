"""Ride lifecycle: start from a booking, pause, resume, finish with a receipt.

Locking (see DEVLOG day 4): start takes FOR UPDATE on the user, then the booking, then the
scooter; pause/resume/finish lock the ride and then the scooter. Repeated identical
transitions are idempotent and return the current state instead of failing.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.billing import Segment, SegmentKind, bill, duration_seconds, segment_cost
from app.geo import Point, point_in_polygon
from app.models import (
    Booking,
    BookingStatus,
    Ride,
    RideSegment,
    RideStatus,
    Scooter,
    ScooterStatus,
    User,
)
from app.services.scooters import status_after_telemetry

UNFINISHED = (RideStatus.ACTIVE, RideStatus.PAUSED)


@dataclass(frozen=True)
class Tariff:
    ride_rate_per_minute: Decimal
    pause_rate_per_minute: Decimal


class RideError(Exception):
    status_code = 400

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class RideNotFoundError(RideError):
    status_code = 404


class RideForbiddenError(RideError):
    status_code = 403


class RideConflictError(RideError):
    status_code = 409


async def get_active_ride(session: AsyncSession, user_id: int) -> Ride | None:
    return await session.scalar(
        select(Ride).where(Ride.user_id == user_id, Ride.status.in_(UNFINISHED))
    )


async def _locked_ride(session: AsyncSession, user_id: int, ride_id: int) -> Ride:
    ride = await session.scalar(select(Ride).where(Ride.id == ride_id).with_for_update(of=Ride))
    if ride is None:
        raise RideNotFoundError("ride_not_found", f"Ride {ride_id} not found")
    if ride.user_id != user_id:
        raise RideForbiddenError("not_your_ride", "This ride belongs to another user")
    return ride


async def _locked_scooter(session: AsyncSession, scooter_id: int) -> Scooter:
    scooter = await session.scalar(
        select(Scooter).where(Scooter.id == scooter_id).with_for_update()
    )
    assert scooter is not None  # foreign key guarantees the row exists
    return scooter


def _open_segment(ride: Ride) -> RideSegment:
    segment = ride.segments[-1]
    assert segment.ended_at is None, "an unfinished ride always has an open segment"
    return segment


def _close_segment(ride: Ride, segment: RideSegment, now: datetime) -> datetime:
    """Close the open segment at `now`, clamped so the timeline never runs backwards.

    `now` is sampled before the row lock; a request that lost the lock race may carry a time
    earlier than the segment it is closing. Clamping bills a zero-second segment instead of
    failing (or billing a negative amount). Returns the effective time.
    """
    now = max(now, segment.started_at)
    rate = (
        ride.ride_rate_per_minute
        if segment.kind is SegmentKind.RIDE
        else ride.pause_rate_per_minute
    )
    segment.ended_at = now
    # Whole seconds since the ride started, differenced: the sub-second remainder of one
    # segment carries into the next instead of being dropped, so the segments always sum to
    # floor(total duration) and toggling pause/resume quickly cannot zero the bill.
    segment.seconds = duration_seconds(ride.started_at, now) - duration_seconds(
        ride.started_at, segment.started_at
    )
    segment.cost = segment_cost(rate, segment.seconds)
    return now


async def _reload(session: AsyncSession, ride_id: int) -> Ride:
    """Fresh copy with all relationships after a commit."""
    session.expire_all()
    ride = await session.get(Ride, ride_id)
    assert ride is not None
    return ride


async def start_ride(
    session: AsyncSession, user_id: int, booking_id: int, tariff: Tariff, now: datetime
) -> tuple[Ride, bool]:
    """Turn the user's active booking into a ride. Returns (ride, created).

    A repeated start for a booking whose ride is still going returns that ride with
    created=False, so a double click or a retried request changes nothing.
    """
    await session.execute(select(User.id).where(User.id == user_id).with_for_update())
    booking = await session.scalar(
        select(Booking).where(Booking.id == booking_id).with_for_update(of=Booking)
    )
    if booking is None:
        raise RideNotFoundError("booking_not_found", f"Booking {booking_id} not found")
    if booking.user_id != user_id:
        raise RideForbiddenError("not_your_booking", "This booking belongs to another user")

    if booking.status is BookingStatus.USED:
        existing = await session.scalar(select(Ride).where(Ride.booking_id == booking_id))
        if existing is not None and existing.status in UNFINISHED:
            return existing, False
        raise RideConflictError("booking_used", "This booking has already been used for a ride")
    if booking.status is not BookingStatus.ACTIVE or booking.expires_at <= now:
        # an expired booking the sweeper has not swept yet counts as expired already
        state = "expired" if booking.status is BookingStatus.ACTIVE else booking.status.value
        raise RideConflictError("booking_not_active", f"Booking is {state}, book the scooter again")
    if await get_active_ride(session, user_id) is not None:
        raise RideConflictError("user_has_active_ride", "You already have a ride in progress")

    scooter = await _locked_scooter(session, booking.scooter_id)
    if scooter.status is not ScooterStatus.RESERVED:
        raise RideConflictError(
            "scooter_not_available", f"Scooter {scooter.code} is {scooter.status.value}"
        )

    ride = Ride(
        user_id=user_id,
        scooter_id=scooter.id,
        booking_id=booking_id,
        started_at=now,
        ride_rate_per_minute=tariff.ride_rate_per_minute,
        pause_rate_per_minute=tariff.pause_rate_per_minute,
        segments=[RideSegment(kind=SegmentKind.RIDE, started_at=now)],
    )
    booking.status = BookingStatus.USED
    scooter.status = ScooterStatus.RIDING
    session.add(ride)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise RideConflictError(
            "user_has_active_ride", "You already have a ride in progress"
        ) from exc
    return await _reload(session, ride.id), True


async def pause_ride(session: AsyncSession, user_id: int, ride_id: int, now: datetime) -> Ride:
    ride = await _locked_ride(session, user_id, ride_id)
    if ride.status is RideStatus.FINISHED:
        raise RideConflictError("ride_finished", "This ride is already finished")
    if ride.status is RideStatus.PAUSED:
        return ride
    scooter = await _locked_scooter(session, ride.scooter_id)
    now = _close_segment(ride, _open_segment(ride), now)
    ride.segments.append(RideSegment(kind=SegmentKind.PAUSE, started_at=now))
    ride.status = RideStatus.PAUSED
    scooter.paused = True
    await session.commit()
    return await _reload(session, ride_id)


async def resume_ride(session: AsyncSession, user_id: int, ride_id: int, now: datetime) -> Ride:
    ride = await _locked_ride(session, user_id, ride_id)
    if ride.status is RideStatus.FINISHED:
        raise RideConflictError("ride_finished", "This ride is already finished")
    if ride.status is RideStatus.ACTIVE:
        return ride
    scooter = await _locked_scooter(session, ride.scooter_id)
    now = _close_segment(ride, _open_segment(ride), now)
    ride.segments.append(RideSegment(kind=SegmentKind.RIDE, started_at=now))
    ride.status = RideStatus.ACTIVE
    scooter.paused = False
    await session.commit()
    return await _reload(session, ride_id)


async def finish_ride(
    session: AsyncSession,
    user_id: int,
    ride_id: int,
    zones: Sequence[Sequence[Point]],
    low_battery_threshold: int,
    now: datetime,
) -> tuple[Ride, bool]:
    """Close the open segment, bill the ride and free the scooter. Returns (ride, finished_now).

    The scooter's own position (last telemetry) must be inside a service zone; the client
    cannot fake it. A ride that is already finished is returned unchanged with finished_now=False.
    """
    ride = await _locked_ride(session, user_id, ride_id)
    if ride.status is RideStatus.FINISHED:
        return ride, False
    scooter = await _locked_scooter(session, ride.scooter_id)
    position = Point(scooter.lat, scooter.lon)
    if not any(point_in_polygon(position, zone) for zone in zones):
        raise RideConflictError(
            "outside_service_zone",
            "The scooter is outside the service zone; return inside it to finish the ride",
        )

    now = _close_segment(ride, _open_segment(ride), now)
    receipt = bill(
        [Segment(s.kind, s.seconds or 0) for s in ride.segments],
        ride.ride_rate_per_minute,
        ride.pause_rate_per_minute,
    )
    ride.ride_seconds = receipt.ride_seconds
    ride.pause_seconds = receipt.pause_seconds
    ride.ride_cost = receipt.ride_cost
    ride.pause_cost = receipt.pause_cost
    ride.total_cost = receipt.total_cost
    ride.finished_at = now
    ride.status = RideStatus.FINISHED
    scooter.status = status_after_telemetry(
        ScooterStatus.AVAILABLE, scooter.battery, low_battery_threshold
    )
    scooter.paused = False
    await session.commit()
    return await _reload(session, ride_id), True
