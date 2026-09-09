from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db
from app.schemas.scooter import ScooterOut, TelemetryIn
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
    """Update position and battery; applies the low-battery rule and returns the new state."""
    scooter = await scooter_service.apply_telemetry(
        session, telemetry, settings.low_battery_threshold
    )
    if scooter is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"Scooter {telemetry.code} not found")
    return ScooterOut.model_validate(scooter)
