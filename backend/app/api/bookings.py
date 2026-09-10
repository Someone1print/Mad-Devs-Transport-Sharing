from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, api_error
from app.core.config import settings
from app.db.session import get_db
from app.realtime.hub import hub, scooter_updated_event
from app.schemas.booking import BookingCreate, BookingOut
from app.schemas.scooter import ScooterOut
from app.services import bookings as booking_service
from app.services.bookings import BookingError

router = APIRouter()

DbSession = Annotated[AsyncSession, Depends(get_db)]


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

    await hub.broadcast(scooter_updated_event(ScooterOut.model_validate(booking.scooter)))
    return BookingOut.from_booking(booking)
