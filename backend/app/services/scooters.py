from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Scooter, ScooterStatus
from app.schemas.scooter import TelemetryIn


def status_after_telemetry(current: ScooterStatus, battery: int, threshold: int) -> ScooterStatus:
    """Business rule for the battery level reported by telemetry.

    A scooter in a ride keeps `riding` whatever the battery says (the rule is applied when the
    ride finishes). Otherwise a battery strictly below the threshold makes the scooter
    unavailable, and an unavailable scooter with a healthy battery becomes available again
    (there is no separate "reason" for unavailability yet). Reserved scooters keep their status
    while the battery is healthy.
    """
    if current is ScooterStatus.RIDING:
        # A ride in progress owns the scooter: telemetry only records the battery. The battery
        # rule is applied once, when the ride finishes (services.rides.finish_ride).
        # TODO(rides): auto-finish the ride with a bill and an e-mail when the battery runs out.
        return current
    if battery < threshold:
        return ScooterStatus.UNAVAILABLE
    if current is ScooterStatus.UNAVAILABLE:
        return ScooterStatus.AVAILABLE
    return current


async def list_scooters(session: AsyncSession) -> Sequence[Scooter]:
    return (await session.scalars(select(Scooter).order_by(Scooter.code))).all()


async def apply_telemetry(
    session: AsyncSession, telemetry: TelemetryIn, threshold: int
) -> Scooter | None:
    """Store the reported position and battery; returns None if the code is unknown."""
    # FOR UPDATE: a ride transition may hold this row; wait for it and read the committed
    # status instead of overwriting it with a stale one (lost update).
    scooter = await session.scalar(
        select(Scooter).where(Scooter.code == telemetry.code).with_for_update()
    )
    if scooter is None:
        return None

    scooter.lat = telemetry.lat
    scooter.lon = telemetry.lon
    scooter.battery = telemetry.battery
    scooter.status = status_after_telemetry(scooter.status, telemetry.battery, threshold)
    await session.commit()
    await session.refresh(scooter)
    return scooter
