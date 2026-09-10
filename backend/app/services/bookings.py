from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Booking, BookingStatus, Scooter, ScooterStatus, User


class BookingError(Exception):
    status_code = 400

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class ScooterNotFoundError(BookingError):
    status_code = 404


class BookingConflictError(BookingError):
    status_code = 409


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
