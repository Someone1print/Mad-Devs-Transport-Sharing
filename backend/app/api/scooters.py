from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import clock
from app.core.config import settings
from app.db.session import get_db
from app.realtime.hub import hub, scooter_updated_event
from app.realtime.publish import announce_receipt, publish_ride_change
from app.schemas.scooter import ScooterOut, TelemetryIn
from app.services import rides as ride_service
from app.services import scooters as scooter_service

router = APIRouter()


@router.get("/scooters", summary="List all scooters")
async def get_scooters(session: Annotated[AsyncSession, Depends(get_db)]) -> list[ScooterOut]:
    """Initial state for the map; live changes arrive over the WebSocket."""
    scooters = await scooter_service.list_scooters(session)
    return [ScooterOut.model_validate(scooter) for scooter in scooters]


@router.post("/telemetry", summary="Accept telemetry from a scooter")
async def post_telemetry(
    telemetry: TelemetryIn, session: Annotated[AsyncSession, Depends(get_db)]
) -> ScooterOut:
    """Update position and battery; applies the low-battery rule and returns the new state.

    A flat battery on a scooter in a ride ends the ride: the rider is told (ride.finished with
    the reason, then the receipt e-mail) and everyone sees the scooter go unavailable.
    """
    result = await ride_service.record_telemetry(
        session,
        telemetry,
        settings.low_battery_threshold,
        settings.ride_auto_finish_battery,
        clock.now(),
    )
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"Scooter {telemetry.code} not found")
    if result.finish is not None:
        await publish_ride_change(result.finish.ride, "ride.finished")
        await announce_receipt(session, result.finish.ride, result.finish.email_id)
        return ScooterOut.model_validate(result.finish.ride.scooter)
    state = ScooterOut.model_validate(result.scooter)
    await hub.broadcast(scooter_updated_event(state))
    return state
