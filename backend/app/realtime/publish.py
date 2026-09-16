"""What the routers announce after a ride transition commits (the rides and telemetry routers)."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Email, Ride
from app.realtime.hub import email_event, hub, ride_event, scooter_updated_event
from app.schemas.email import EmailOut
from app.schemas.ride import RideOut
from app.schemas.scooter import ScooterOut


async def publish_ride_change(ride: Ride, event_type: str) -> RideOut:
    """Everyone learns the scooter's new state; the rider gets the ride event."""
    out = RideOut.from_ride(ride)
    await hub.broadcast(scooter_updated_event(ScooterOut.model_validate(ride.scooter)))
    await hub.send_to_user(ride.user_id, ride_event(event_type, out))
    return out


async def announce_receipt(session: AsyncSession, ride: Ride, email_id: int | None) -> None:
    """Announced when stored: right after the finish, or on the retry that healed it."""
    if email_id is None:
        return
    email = await session.get(Email, email_id)
    if email is not None:
        await hub.send_to_user(ride.user_id, email_event(EmailOut.model_validate(email)))
