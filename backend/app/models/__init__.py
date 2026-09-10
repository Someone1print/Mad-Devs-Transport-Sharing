"""ORM models. Import every model module here so Alembic autogenerate can see all tables."""

from app.db.base import Base
from app.models.scooter import Scooter, ScooterStatus
from app.models.user import User

__all__ = ["Base", "Scooter", "ScooterStatus", "User"]
