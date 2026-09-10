from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, api_error
from app.core.config import settings
from app.db.session import get_db
from app.models import Booking
from app.realtime.hub import booking_event, hub, scooter_updated_event
from app.schemas.booking import BookingCreate, BookingOut
from app.schemas.scooter import ScooterOut
from app.services import bookings as booking_service
from app.services.bookings import BookingError

router = APIRouter()

DbSession = Annotated[AsyncSession, Depends(get_db)]


async def publish_booking_change(booking: Booking, event_type: str) -> BookingOut:
    """Tell everyone about the scooter and the owner about the booking."""
    out = BookingOut.from_booking(booking)
    await hub.broadcast(scooter_updated_event(ScooterOut.model_validate(booking.scooter)))
    await hub.send_to_user(booking.user_id, booking_event(event_type, out))
    return out


@router.post("/bookings", status_code=status.HTTP_201_CREATED, summary="Book a scooter")
async def create_booking(
    payload: BookingCreate, user: CurrentUser, session: DbSession
) -> BookingOut:
    """Reserve an available scooter for BOOKING_TTL_SECONDS; everyone sees it turn `reserved`."""
    try:
        booking = await booking_service.create_booking(
            session,
            user_id=user.id,
            scooter_code=payload.scooter_code,
            ttl=timedelta(seconds=settings.booking_ttl_seconds),
            now=datetime.now(UTC),
        )
    except BookingError as exc:
        raise HTTPException(exc.status_code, detail=api_error(exc.code, exc.message)) from exc
    return await publish_booking_change(booking, "booking.created")


@router.get("/bookings/active", summary="The caller's active booking, if any")
async def get_active_booking(user: CurrentUser, session: DbSession) -> BookingOut | None:
    booking = await booking_service.get_active_booking(session, user.id)
    return BookingOut.from_booking(booking) if booking is not None else None


@router.post("/bookings/{booking_id}/cancel", summary="Cancel own booking")
async def cancel_booking(booking_id: int, user: CurrentUser, session: DbSession) -> BookingOut:
    try:
        booking = await booking_service.cancel_booking(
            session, user_id=user.id, booking_id=booking_id, now=datetime.now(UTC)
        )
    except BookingError as exc:
        raise HTTPException(exc.status_code, detail=api_error(exc.code, exc.message)) from exc
    return await publish_booking_change(booking, "booking.cancelled")
