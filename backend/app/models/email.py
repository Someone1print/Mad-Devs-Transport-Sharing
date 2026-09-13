from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Email(Base):
    """An outgoing e-mail, stored instead of sent (the assignment allows a mailbox stub).

    `dedup_key` is unique: `services.mail.send_email` inserts with ON CONFLICT DO NOTHING, so
    one key can never produce two messages — the same idea as `warned_at` on bookings.
    """

    __tablename__ = "emails"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    to_address: Mapped[str] = mapped_column(String(255))
    subject: Mapped[str] = mapped_column(String(255))
    body: Mapped[str] = mapped_column(Text)
    dedup_key: Mapped[str] = mapped_column(String(128), unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp()
    )
