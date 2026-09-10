from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models import ScooterStatus


class ScooterOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    lat: float
    lon: float
    battery: int
    status: ScooterStatus
    updated_at: datetime


class TelemetryIn(BaseModel):
    """What a scooter reports about itself."""

    code: str = Field(min_length=1, max_length=32)
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    battery: int = Field(ge=0, le=100, description="Charge level in percent")
