import enum
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Double,
    Enum,
    SmallInteger,
    String,
    false,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ScooterStatus(enum.StrEnum):
    AVAILABLE = "available"  # свободен
    RESERVED = "reserved"  # забронирован
    RIDING = "riding"  # в поездке
    UNAVAILABLE = "unavailable"  # недоступен (например, низкий заряд)


class Scooter(Base):
    __tablename__ = "scooters"
    __table_args__ = (CheckConstraint("battery BETWEEN 0 AND 100", name="battery_range"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True)
    lat: Mapped[float] = mapped_column(Double)
    lon: Mapped[float] = mapped_column(Double)
    battery: Mapped[int] = mapped_column(SmallInteger)
    status: Mapped[ScooterStatus] = mapped_column(
        Enum(ScooterStatus, name="scooter_status", values_callable=lambda e: [m.value for m in e]),
        default=ScooterStatus.AVAILABLE,
        server_default=ScooterStatus.AVAILABLE.value,
    )
    # The ride on this scooter is paused (set by ride pause/resume/finish under the row lock);
    # a real column so that pausing bumps updated_at and clients cannot apply it out of order.
    paused: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    # clock_timestamp() is the real wall-clock time of the write; now() would be the transaction
    # start and could not distinguish two updates made in the same transaction.
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.clock_timestamp(),
        onupdate=func.clock_timestamp(),
    )
