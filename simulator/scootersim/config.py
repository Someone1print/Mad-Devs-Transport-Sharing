import os
from collections.abc import Mapping
from dataclasses import dataclass, fields, replace

ENV_NAMES = {
    "backend_url": "BACKEND_URL",
    "active_scooters": "SIM_ACTIVE_SCOOTERS",
    "interval_seconds": "SIM_INTERVAL_SECONDS",
    "speed_kmh": "SIM_SPEED_KMH",
    "drain_per_km": "SIM_DRAIN_PER_KM",
    "recharge_seconds": "SIM_RECHARGE_SECONDS",
    "min_ride_battery": "SIM_MIN_RIDE_BATTERY",
    "heartbeat_ticks": "SIM_HEARTBEAT_TICKS",
    "refresh_every_ticks": "SIM_REFRESH_TICKS",
    "held_heartbeat_ticks": "SIM_HELD_HEARTBEAT_TICKS",
}


@dataclass(frozen=True)
class Config:
    backend_url: str = "http://localhost:8000"
    active_scooters: int = 6  # how many scooters ride at any moment
    interval_seconds: float = 1.5  # tick and telemetry period
    speed_kmh: float = 40.0  # exaggerated so movement is visible on the map
    drain_per_km: float = 4.0  # battery percent per kilometre (exaggerated for the demo)
    recharge_seconds: float = 180.0  # how long a "technician" needs to swap the battery
    min_ride_battery: int = 20  # idle scooters below this do not start rides
    heartbeat_ticks: int = 20  # idle scooters report every N ticks
    refresh_every_ticks: int = 10  # re-read scooter statuses from the backend every N ticks
    held_heartbeat_ticks: int = 2  # reserved / paused scooters report every N ticks

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "Config":
        source = os.environ if env is None else env
        values: dict[str, object] = {}
        for field in fields(cls):
            raw = source.get(ENV_NAMES[field.name])
            if raw is not None:
                values[field.name] = field.type(raw)  # type: ignore[operator]
        config = cls(**values)  # type: ignore[arg-type]
        return replace(config, backend_url=config.backend_url.rstrip("/"))
