import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, api_error
from app.core import clock
from app.core.config import settings
from app.db.session import get_db
from app.models import Ride, ServiceZone
from app.realtime.hub import hub, ride_event, scooter_updated_event
from app.schemas.ride import RideOut, RideStart
from app.schemas.scooter import ScooterOut
from app.services import rides as ride_service
from app.services.rides import RideError, Tariff

router = APIRouter()
logger = logging.getLogger(__name__)

DbSession = Annotated[AsyncSession, Depends(get_db)]


def current_tariff() -> Tariff:
    return Tariff(
        ride_rate_per_minute=settings.ride_rate_per_minute,
        pause_rate_per_minute=settings.pause_rate_per_minute,
    )


async def publish_ride_change(ride: Ride, event_type: str) -> RideOut:
    """Everyone learns the scooter's new state; the rider gets the ride event."""
    out = RideOut.from_ride(ride)
    await hub.broadcast(scooter_updated_event(ScooterOut.model_validate(ride.scooter)))
    await hub.send_to_user(ride.user_id, ride_event(event_type, out))
    return out


def http_error(exc: RideError) -> HTTPException:
    return HTTPException(exc.status_code, detail=api_error(exc.code, exc.message))


@router.post("/rides", status_code=status.HTTP_201_CREATED, summary="Start a ride from a booking")
async def start_ride(
    payload: RideStart, user: CurrentUser, session: DbSession, response: Response
) -> RideOut:
    """201 with the new ride; 200 with the existing one when the booking's ride is already going."""
    try:
        ride, created = await ride_service.start_ride(
            session, user.id, payload.booking_id, current_tariff(), clock.now()
        )
    except RideError as exc:
        raise http_error(exc) from exc
    if not created:
        response.status_code = status.HTTP_200_OK
        return RideOut.from_ride(ride)
    return await publish_ride_change(ride, "ride.started")


@router.get("/rides/active", summary="The caller's ride in progress, if any")
async def get_active_ride(user: CurrentUser, session: DbSession) -> RideOut | None:
    ride = await ride_service.get_active_ride(session, user.id)
    return RideOut.from_ride(ride) if ride is not None else None


@router.post("/rides/{ride_id}/pause", summary="Pause the ride (pause tariff applies)")
async def pause_ride(ride_id: int, user: CurrentUser, session: DbSession) -> RideOut:
    try:
        ride = await ride_service.pause_ride(session, user.id, ride_id, clock.now())
    except RideError as exc:
        raise http_error(exc) from exc
    return await publish_ride_change(ride, "ride.paused")


@router.post("/rides/{ride_id}/resume", summary="Resume a paused ride")
async def resume_ride(ride_id: int, user: CurrentUser, session: DbSession) -> RideOut:
    try:
        ride = await ride_service.resume_ride(session, user.id, ride_id, clock.now())
    except RideError as exc:
        raise http_error(exc) from exc
    return await publish_ride_change(ride, "ride.resumed")


@router.post("/rides/{ride_id}/finish", summary="Finish the ride inside a service zone")
async def finish_ride(ride_id: int, user: CurrentUser, session: DbSession) -> RideOut:
    """409 outside_service_zone when the scooter is not inside any zone; idempotent when done."""
    zones = [z.as_points() for z in (await session.scalars(select(ServiceZone))).all()]
    if not zones:
        # fail closed (no ride can end) but say why: the seed should have inserted a zone
        logger.warning("No service zones configured: every finish will be refused")
    try:
        ride, finished_now = await ride_service.finish_ride(
            session, user.id, ride_id, zones, settings.low_battery_threshold, clock.now()
        )
    except RideError as exc:
        raise http_error(exc) from exc
    if not finished_now:
        return RideOut.from_ride(ride)
    return await publish_ride_change(ride, "ride.finished")
