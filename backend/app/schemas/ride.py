from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.billing import CURRENCY, SegmentKind
from app.models import Ride, RideStatus


class RideStart(BaseModel):
    booking_id: int = Field(gt=0)


class RideSegmentOut(BaseModel):
    kind: SegmentKind
    started_at: datetime
    ended_at: datetime | None
    seconds: int | None
    cost: Decimal | None


class ReceiptOut(BaseModel):
    ride_seconds: int
    pause_seconds: int
    ride_cost: Decimal
    pause_cost: Decimal
    total_cost: Decimal
    currency: str = CURRENCY


class RideOut(BaseModel):
    """A ride with its tariff snapshot and segments; `receipt` is set once it is finished.

    Money is serialised as strings ("7.50") so no client ever parses it into a float.
    """

    id: int
    scooter_code: str
    user_id: int
    status: RideStatus
    started_at: datetime
    finished_at: datetime | None
    ride_rate_per_minute: Decimal
    pause_rate_per_minute: Decimal
    segments: list[RideSegmentOut]
    receipt: ReceiptOut | None

    @classmethod
    def from_ride(cls, ride: Ride) -> "RideOut":
        receipt = None
        if ride.status is RideStatus.FINISHED:
            assert ride.total_cost is not None
            receipt = ReceiptOut(
                ride_seconds=ride.ride_seconds or 0,
                pause_seconds=ride.pause_seconds or 0,
                ride_cost=ride.ride_cost or Decimal("0.00"),
                pause_cost=ride.pause_cost or Decimal("0.00"),
                total_cost=ride.total_cost,
            )
        return cls(
            id=ride.id,
            scooter_code=ride.scooter.code,
            user_id=ride.user_id,
            status=ride.status,
            started_at=ride.started_at,
            finished_at=ride.finished_at,
            ride_rate_per_minute=ride.ride_rate_per_minute,
            pause_rate_per_minute=ride.pause_rate_per_minute,
            segments=[
                RideSegmentOut(
                    kind=s.kind,
                    started_at=s.started_at,
                    ended_at=s.ended_at,
                    seconds=s.seconds,
                    cost=s.cost,
                )
                for s in ride.segments
            ],
            receipt=receipt,
        )
