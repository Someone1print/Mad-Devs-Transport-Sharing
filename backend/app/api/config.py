from decimal import Decimal

from fastapi import APIRouter
from pydantic import BaseModel

from app.billing import CURRENCY
from app.core.config import settings

router = APIRouter()


class PublicConfig(BaseModel):
    booking_ttl_seconds: int
    booking_warn_before_seconds: int
    low_battery_threshold: int
    ride_rate_per_minute: Decimal
    pause_rate_per_minute: Decimal
    currency: str


@router.get("/config", summary="Public runtime settings the UI needs")
async def get_config() -> PublicConfig:
    return PublicConfig(
        booking_ttl_seconds=settings.booking_ttl_seconds,
        booking_warn_before_seconds=settings.booking_warn_before_seconds,
        low_battery_threshold=settings.low_battery_threshold,
        ride_rate_per_minute=settings.ride_rate_per_minute,
        pause_rate_per_minute=settings.pause_rate_per_minute,
        currency=CURRENCY,
    )
