from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class User(Base):
    """A rider: display name, e-mail (the login) and an argon2 password hash.

    `password_hash` is None only on rows created before accounts had passwords; such a row is
    an account waiting to be claimed at registration (services/auth.py) and cannot sign in.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64))
    # the login and the receipt address, stored lower-case; None only on legacy rows, whose
    # receipts go to the name-derived stub
    email: Mapped[str | None] = mapped_column(String(254))
    password_hash: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp()
    )
