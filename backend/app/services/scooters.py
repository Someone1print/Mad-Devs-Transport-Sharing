from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Scooter, ScooterStatus
from app.schemas.scooter import TelemetryIn


def status_after_telemetry(current: ScooterStatus, battery: int, threshold: int) -> ScooterStatus:
    """Business rule for the battery level reported by telemetry.

    A battery strictly below the threshold always makes the scooter unavailable. A scooter that
    was unavailable and now reports a healthy battery becomes available again (there is no
    separate "reason" for unavailability yet). Reserved and riding scooters keep their status.
    """
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
    scooter = await session.scalar(select(Scooter).where(Scooter.code == telemetry.code))
    if scooter is None:
        return None

    scooter.lat = telemetry.lat
    scooter.lon = telemetry.lon
    scooter.battery = telemetry.battery
    scooter.status = status_after_telemetry(scooter.status, telemetry.battery, threshold)
    await session.commit()
    await session.refresh(scooter)
    return scooter
