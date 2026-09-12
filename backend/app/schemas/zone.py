from pydantic import BaseModel, ConfigDict

from app.models import ServiceZone


class ZonePoint(BaseModel):
    lat: float
    lon: float


class ZoneOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    points: list[ZonePoint]

    @classmethod
    def from_zone(cls, zone: ServiceZone) -> "ZoneOut":
        return cls(id=zone.id, name=zone.name, points=[ZonePoint(**p) for p in zone.points])
