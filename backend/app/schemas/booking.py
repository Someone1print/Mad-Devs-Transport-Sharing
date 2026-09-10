from datetime import datetime

from pydantic import BaseModel, Field

from app.models import Booking, BookingStatus


class BookingCreate(BaseModel):
    scooter_code: str = Field(min_length=1, max_length=32)


class BookingOut(BaseModel):
    id: int
    scooter_code: str
    user_id: int
    status: BookingStatus
    created_at: datetime
    expires_at: datetime

    @classmethod
    def from_booking(cls, booking: Booking) -> "BookingOut":
        return cls(
            id=booking.id,
            scooter_code=booking.scooter.code,
            user_id=booking.user_id,
            status=booking.status,
            created_at=booking.created_at,
            expires_at=booking.expires_at,
        )
