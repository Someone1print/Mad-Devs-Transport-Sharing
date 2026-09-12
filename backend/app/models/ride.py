import enum
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, Numeric, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.billing import SegmentKind
from app.db.base import Base
from app.models.booking import Booking
from app.models.scooter import Scooter
from app.models.user import User


class RideStatus(enum.StrEnum):
    ACTIVE = "active"  # едет
    PAUSED = "paused"  # на паузе, самокат стоит, идёт тариф паузы
    FINISHED = "finished"  # завершена, чек выставлен


MONEY = Numeric(10, 2)
RATE = Numeric(8, 2)


class Ride(Base):
    """A ride started from a booking. Billing is the sum of its segments (see app.billing).

    The tariff is snapshotted at start so a later rate change never alters a running ride,
    and the receipt stays reproducible. Partial unique indexes keep one unfinished ride per
    user and per scooter behind the row locks taken in `services.rides`.
    """

    __tablename__ = "rides"
    __table_args__ = (
        Index(
            "uq_rides_unfinished_user",
            "user_id",
            unique=True,
            postgresql_where=text("status <> 'finished'"),
        ),
        Index(
            "uq_rides_unfinished_scooter",
            "scooter_id",
            unique=True,
            postgresql_where=text("status <> 'finished'"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    scooter_id: Mapped[int] = mapped_column(ForeignKey("scooters.id"))
    booking_id: Mapped[int] = mapped_column(ForeignKey("bookings.id"), unique=True)
    status: Mapped[RideStatus] = mapped_column(
        Enum(RideStatus, name="ride_status", values_callable=lambda e: [m.value for m in e]),
        default=RideStatus.ACTIVE,
        server_default=RideStatus.ACTIVE.value,
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # tariff snapshot, per minute
    ride_rate_per_minute: Mapped[Decimal] = mapped_column(RATE)
    pause_rate_per_minute: Mapped[Decimal] = mapped_column(RATE)
    # receipt, filled when the ride finishes
    ride_seconds: Mapped[int | None] = mapped_column(Integer)
    pause_seconds: Mapped[int | None] = mapped_column(Integer)
    ride_cost: Mapped[Decimal | None] = mapped_column(MONEY)
    pause_cost: Mapped[Decimal | None] = mapped_column(MONEY)
    total_cost: Mapped[Decimal | None] = mapped_column(MONEY)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp()
    )

    user: Mapped[User] = relationship(lazy="joined")
    scooter: Mapped[Scooter] = relationship(lazy="joined")
    booking: Mapped[Booking] = relationship(lazy="joined")
    segments: Mapped[list["RideSegment"]] = relationship(
        back_populates="ride",
        order_by="RideSegment.started_at, RideSegment.id",
        lazy="selectin",
        cascade="all, delete-orphan",
    )


class RideSegment(Base):
    """One stretch of riding or pausing. `seconds` and `cost` are set when the segment closes."""

    __tablename__ = "ride_segments"

    id: Mapped[int] = mapped_column(primary_key=True)
    ride_id: Mapped[int] = mapped_column(ForeignKey("rides.id", ondelete="CASCADE"), index=True)
    kind: Mapped[SegmentKind] = mapped_column(
        Enum(SegmentKind, name="segment_kind", values_callable=lambda e: [m.value for m in e])
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    seconds: Mapped[int | None] = mapped_column(Integer)
    cost: Mapped[Decimal | None] = mapped_column(MONEY)

    ride: Mapped[Ride] = relationship(back_populates="segments")
