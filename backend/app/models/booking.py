import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.scooter import Scooter
from app.models.user import User


class BookingStatus(enum.StrEnum):
    ACTIVE = "active"
    CANCELLED = "cancelled"  # отменена пользователем
    EXPIRED = "expired"  # снята автоматически по истечении срока


class Booking(Base):
    """A hold on a scooter for one user. Exactly one active booking per scooter and per user.

    The partial unique indexes are the database-level safety net behind the row locks taken
    in `services.bookings.create_booking`.
    """

    __tablename__ = "bookings"
    __table_args__ = (
        Index(
            "uq_bookings_active_scooter",
            "scooter_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
        Index(
            "uq_bookings_active_user",
            "user_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    scooter_id: Mapped[int] = mapped_column(ForeignKey("scooters.id"))
    status: Mapped[BookingStatus] = mapped_column(
        Enum(BookingStatus, name="booking_status", values_callable=lambda e: [m.value for m in e]),
        default=BookingStatus.ACTIVE,
        server_default=BookingStatus.ACTIVE.value,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp()
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # when the "expiring soon" notification was sent; NULL until then (persisted deduplication)
    warned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship(lazy="joined")
    scooter: Mapped[Scooter] = relationship(lazy="joined")
