"""Background maintenance of bookings, driven by `expires_at` stored in the database.

Nothing is kept in memory: every iteration reads the state from the database, so a restart
of the backend loses no timers and the first iteration after start catches up with anything
missed while the process was down.
"""

import asyncio
import contextlib
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Booking, BookingStatus, Scooter, ScooterStatus
from app.realtime.hub import ScooterHub, booking_event, scooter_updated_event
from app.schemas.booking import BookingOut
from app.schemas.scooter import ScooterOut
from app.services.scooters import release_status

logger = logging.getLogger(__name__)

SessionFactory = Callable[[], AsyncSession]


@dataclass
class SweepResult:
    expired: list[Booking] = field(default_factory=list)
    warned: list[Booking] = field(default_factory=list)


async def _expire_overdue(
    session: AsyncSession, now: datetime, low_battery_threshold: int
) -> list[Booking]:
    """Mark active bookings past `expires_at` as expired and free their scooters."""
    overdue = (
        (
            await session.scalars(
                select(Booking)
                .where(Booking.status == BookingStatus.ACTIVE, Booking.expires_at <= now)
                .with_for_update(of=Booking, skip_locked=True)
            )
        )
        .unique()
        .all()
    )
    for booking in overdue:
        booking.status = BookingStatus.EXPIRED
        booking.ended_at = now
        scooter = await session.scalar(
            select(Scooter)
            .where(Scooter.id == booking.scooter_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if scooter is not None and scooter.status is ScooterStatus.RESERVED:
            scooter.status = release_status(scooter.battery, low_battery_threshold)
    await session.commit()
    for booking in overdue:
        await session.refresh(booking)
    return list(overdue)


async def _warn_expiring(
    session: AsyncSession, now: datetime, warn_before: timedelta
) -> list[Booking]:
    """Stamp `warned_at` atomically and return only the bookings this call claimed.

    The warning goes out when less than `warn_before` remains, but never earlier than half of
    the booking's own length: a 60-second booking is warned at 30 seconds left, not the moment
    it is created. `WHERE warned_at IS NULL` makes the notification exactly-once across
    iterations, restarts and even several sweeper processes: each row can be claimed by one
    UPDATE only.
    """
    window = func.least(warn_before, (Booking.expires_at - Booking.created_at) / 2)
    claimed = (
        update(Booking)
        .where(
            Booking.status == BookingStatus.ACTIVE,
            Booking.warned_at.is_(None),
            Booking.expires_at > now,
            Booking.expires_at - now <= window,
        )
        .values(warned_at=now)
        .returning(Booking.id)
    )
    ids = (await session.scalars(claimed)).all()
    await session.commit()
    if not ids:
        return []
    return list((await session.scalars(select(Booking).where(Booking.id.in_(ids)))).unique().all())


async def sweep_bookings(
    session: AsyncSession,
    hub: ScooterHub,
    now: datetime,
    warn_before: timedelta,
    low_battery_threshold: int,
) -> SweepResult:
    """One maintenance pass: expire overdue bookings, then warn about the ones expiring soon."""
    result = SweepResult(
        expired=await _expire_overdue(session, now, low_battery_threshold),
        warned=await _warn_expiring(session, now, warn_before),
    )
    for booking in result.expired:
        await hub.broadcast(scooter_updated_event(ScooterOut.model_validate(booking.scooter)))
        await hub.send_to_user(
            booking.user_id, booking_event("booking.expired", BookingOut.from_booking(booking))
        )
    for booking in result.warned:
        seconds_left = max(0, int((booking.expires_at - now).total_seconds()))
        await hub.send_to_user(
            booking.user_id,
            booking_event(
                "booking.expiring", BookingOut.from_booking(booking), seconds_left=seconds_left
            ),
        )
    if result.expired or result.warned:
        logger.info("Booking sweep: expired %d, warned %d", len(result.expired), len(result.warned))
    return result


async def run_booking_sweeper(
    session_factory: SessionFactory,
    hub: ScooterHub,
    interval: float,
    warn_before: timedelta,
    low_battery_threshold: int,
    stop: asyncio.Event | None = None,
) -> None:
    """Run `sweep_bookings` every `interval` seconds until `stop` is set (forever if None).

    Errors are logged and the loop goes on, so a database hiccup never kills the sweeper.
    """
    stop = stop or asyncio.Event()
    while not stop.is_set():
        try:
            async with session_factory() as session:
                await sweep_bookings(
                    session, hub, datetime.now(UTC), warn_before, low_battery_threshold
                )
        except Exception:
            logger.exception("Booking sweep failed; will retry")
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(stop.wait(), timeout=interval)
