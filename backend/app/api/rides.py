import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, api_error
from app.core import clock
from app.core.config import settings
from app.db.session import get_db
from app.models import ServiceZone
from app.realtime.publish import announce_receipt, publish_ride_change
from app.schemas.ride import RideOut, RideStart
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


def http_error(exc: RideError) -> HTTPException:
    return HTTPException(exc.status_code, detail=api_error(exc.code, exc.message))


@router.post("/rides", status_code=status.HTTP_201_CREATED, summary="Start a ride from a booking")
async def start_ride(
    payload: RideStart, user: CurrentUser, session: DbSession, response: Response
) -> RideOut:
    """201 with the new ride; 200 with the existing one when the booking's ride is already going."""
    try:
        ride, created = await ride_service.start_ride(
            session,
            user.id,
            payload.booking_id,
            current_tariff(),
            clock.now(),
            low_battery_threshold=settings.low_battery_threshold,
        )
    except RideError as exc:
        raise http_error(exc) from exc
    if not created:
        response.status_code = status.HTTP_200_OK
        return RideOut.from_ride(ride)
    return await publish_ride_change(ride, "ride.started")


@router.get("/rides", summary="The caller's finished rides, newest first")
async def list_rides(user: CurrentUser, session: DbSession) -> list[RideOut]:
    rides = await ride_service.list_finished_rides(session, user.id)
    return [RideOut.from_ride(ride) for ride in rides]


@router.get("/rides/active", summary="The caller's ride in progress, if any")
async def get_active_ride(user: CurrentUser, session: DbSession) -> RideOut | None:
    ride = await ride_service.get_active_ride(session, user.id)
    return RideOut.from_ride(ride) if ride is not None else None


@router.get("/rides/{ride_id}", summary="One of the caller's rides")
async def get_ride(ride_id: int, user: CurrentUser, session: DbSession) -> RideOut:
    """The client asks for a ride it remembers as active and finds it finished while it was away."""
    try:
        ride = await ride_service.get_ride(session, user.id, ride_id)
    except RideError as exc:
        raise http_error(exc) from exc
    return RideOut.from_ride(ride)


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
        ride, finished_now, email_id = await ride_service.finish_ride(
            session, user.id, ride_id, zones, settings.low_battery_threshold, clock.now()
        )
    except RideError as exc:
        raise http_error(exc) from exc
    out = (
        await publish_ride_change(ride, "ride.finished")
        if finished_now
        else RideOut.from_ride(ride)
    )
    await announce_receipt(session, ride, email_id)
    return out
