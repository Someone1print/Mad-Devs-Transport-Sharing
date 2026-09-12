from typing import Any

from sqlalchemy import String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.geo import Point


class ServiceZone(Base):
    """A polygon inside which rides may be finished. Points are stored as [{lat, lon}, ...]."""

    __tablename__ = "service_zones"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)
    points: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)

    def as_points(self) -> list[Point]:
        return [Point(float(p["lat"]), float(p["lon"])) for p in self.points]
