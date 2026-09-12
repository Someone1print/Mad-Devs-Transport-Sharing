"""ORM models. Import every model module here so Alembic autogenerate can see all tables."""

from app.billing import SegmentKind
from app.db.base import Base
from app.models.booking import Booking, BookingStatus
from app.models.ride import Ride, RideSegment, RideStatus
from app.models.scooter import Scooter, ScooterStatus
from app.models.user import User
from app.models.zone import ServiceZone

__all__ = [
    "Base",
    "Booking",
    "BookingStatus",
    "Ride",
    "RideSegment",
    "RideStatus",
    "Scooter",
    "ScooterStatus",
    "SegmentKind",
    "ServiceZone",
    "User",
]
