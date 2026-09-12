from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Booking, BookingStatus, Ride, RideStatus, Scooter, ScooterStatus, User


class BookingError(Exception):
    status_code = 400

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class ScooterNotFoundError(BookingError):
    status_code = 404


class BookingNotFoundError(BookingError):
    status_code = 404


class BookingForbiddenError(BookingError):
    status_code = 403


class BookingConflictError(BookingError):
    status_code = 409


async def get_active_booking(session: AsyncSession, user_id: int) -> Booking | None:
    return await session.scalar(
        select(Booking).where(Booking.user_id == user_id, Booking.status == BookingStatus.ACTIVE)
    )


async def create_booking(
    session: AsyncSession, user_id: int, scooter_code: str, ttl: timedelta, now: datetime
) -> Booking:
    """Reserve an available scooter for the user until `now + ttl`.

    Concurrency: the user row and then the scooter row are locked with SELECT ... FOR UPDATE
    (always in that order, so two requests can never deadlock). A concurrent request for the
    same scooter waits on the lock, re-reads the row after this transaction commits, sees
    `reserved` and gets a conflict. The partial unique indexes on active bookings turn any
    remaining race into an IntegrityError, reported as the same conflict.
    """
    await session.execute(select(User.id).where(User.id == user_id).with_for_update())
    scooter = await session.scalar(
        select(Scooter).where(Scooter.code == scooter_code).with_for_update()
    )
    if scooter is None:
        raise ScooterNotFoundError("scooter_not_found", f"Scooter {scooter_code} not found")
    if scooter.status is not ScooterStatus.AVAILABLE:
        raise BookingConflictError(
            "scooter_not_available", f"Scooter {scooter_code} is {scooter.status.value}"
        )
    active = await session.scalar(
        select(Booking.id).where(Booking.user_id == user_id, Booking.status == BookingStatus.ACTIVE)
    )
    if active is not None:
        raise BookingConflictError("user_has_active_booking", "You already have an active booking")
    riding = await session.scalar(
        select(Ride.id).where(Ride.user_id == user_id, Ride.status != RideStatus.FINISHED)
    )
    if riding is not None:
        raise BookingConflictError("user_has_active_ride", "Finish your current ride first")

    booking = Booking(user_id=user_id, scooter_id=scooter.id, expires_at=now + ttl)
    scooter.status = ScooterStatus.RESERVED
    session.add(booking)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        if "uq_bookings_active_user" in str(exc.orig):
            raise BookingConflictError(
                "user_has_active_booking", "You already have an active booking"
            ) from exc
        raise BookingConflictError(
            "scooter_not_available", f"Scooter {scooter_code} was just booked by someone else"
        ) from exc
    await session.refresh(booking)
    return booking


async def cancel_booking(
    session: AsyncSession, user_id: int, booking_id: int, now: datetime
) -> Booking:
    """Cancel the caller's active booking and free the scooter.

    The booking row is locked so that a concurrent sweeper iteration cannot expire it at the
    same moment; the scooter goes back to `available` only if it is still `reserved`.
    """
    booking = await session.scalar(
        select(Booking).where(Booking.id == booking_id).with_for_update(of=Booking)
    )
    if booking is None:
        raise BookingNotFoundError("booking_not_found", f"Booking {booking_id} not found")
    if booking.user_id != user_id:
        raise BookingForbiddenError("not_your_booking", "This booking belongs to another user")
    if booking.status is not BookingStatus.ACTIVE:
        raise BookingConflictError("booking_not_active", "This booking is no longer active")

    scooter = await session.scalar(
        select(Scooter).where(Scooter.id == booking.scooter_id).with_for_update()
    )
    booking.status = BookingStatus.CANCELLED
    booking.ended_at = now
    if scooter is not None and scooter.status is ScooterStatus.RESERVED:
        scooter.status = ScooterStatus.AVAILABLE
    await session.commit()
    await session.refresh(booking)
    return booking
