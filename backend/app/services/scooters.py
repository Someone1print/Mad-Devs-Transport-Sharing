from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Scooter, ScooterStatus
from app.schemas.scooter import TelemetryIn

# Statuses in which a user holds the scooter; telemetry never changes them.
HELD = (ScooterStatus.RESERVED, ScooterStatus.RIDING)


def release_status(battery: int, threshold: int) -> ScooterStatus:
    """Status of a scooter a user just let go of: available unless the battery is flat."""
    return ScooterStatus.UNAVAILABLE if battery < threshold else ScooterStatus.AVAILABLE


def status_after_telemetry(current: ScooterStatus, battery: int, threshold: int) -> ScooterStatus:
    """Business rule for the battery level reported by telemetry.

    A held scooter (reserved or in a ride) keeps its status whatever the battery says: the
    rule is applied when the hold is released (cancel, expiry, finish) and when a ride starts.
    Otherwise a battery strictly below the threshold makes the scooter unavailable, and an
    unavailable scooter with a healthy battery becomes available again (there is no separate
    "reason" for unavailability yet).
    """
    if current in HELD:
        # The user owns the scooter: telemetry only records the battery.
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
