import random
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from scootersim.config import Config
from scootersim.geo import BISHKEK_BBOX, haversine_km, random_point, step_towards


class Phase(StrEnum):
    IDLE = "idle"
    RIDING = "riding"
    CHARGING = "charging"  # the backend marked it unavailable; a technician is on the way


@dataclass
class SimScooter:
    code: str
    lat: float
    lon: float
    battery: float
    phase: Phase = Phase.IDLE
    target: tuple[float, float] | None = None
    charging_until: float | None = None
    idle_ticks: int = 0
    parked: bool = False  # reserved or ridden by a real user: never moved by the simulator

    @property
    def battery_percent(self) -> int:
        return max(0, min(100, round(self.battery)))


class Fleet:
    """Local state of the simulated scooters; `tick` advances it and says who must report."""

    def __init__(self, scooters: Iterable[SimScooter], config: Config, rng: random.Random) -> None:
        self.scooters = list(scooters)
        self.config = config
        self.rng = rng
        self._by_code = {scooter.code: scooter for scooter in self.scooters}

    @classmethod
    def from_server(
        cls, payload: list[dict[str, Any]], config: Config, rng: random.Random, now: float
    ) -> "Fleet":
        scooters = [
            SimScooter(item["code"], item["lat"], item["lon"], float(item["battery"]))
            for item in payload
        ]
        fleet = cls(scooters, config, rng)
        for item in payload:
            fleet.apply_server_status(item["code"], item.get("status", ""), now)
        return fleet

    def start_ride(self, scooter: SimScooter, target: tuple[float, float], now: float) -> None:
        del now  # rides do not depend on wall-clock time yet
        scooter.phase = Phase.RIDING
        scooter.target = target
        scooter.idle_ticks = 0

    def apply_server_status(self, code: str, status: str, now: float) -> None:
        """React to the status the backend reports back after telemetry or in the list."""
        scooter = self._by_code.get(code)
        if scooter is None:
            return
        if status == "unavailable":
            scooter.parked = False
            if scooter.phase is not Phase.CHARGING:
                scooter.phase = Phase.CHARGING
                scooter.target = None
                scooter.charging_until = now + self.config.recharge_seconds
        elif status in {"reserved", "riding"}:
            # someone holds the scooter: it stays where it is until the backend frees it
            scooter.parked = True
            if scooter.phase is Phase.RIDING:
                scooter.phase = Phase.IDLE
                scooter.target = None
        elif status == "available":
            scooter.parked = False

    def refresh_statuses(self, payload: list[dict[str, Any]], now: float) -> None:
        """Apply statuses from a fresh GET /api/scooters; unknown codes are ignored."""
        for item in payload:
            self.apply_server_status(str(item.get("code", "")), str(item.get("status", "")), now)

    def tick(self, dt: float, now: float) -> list[SimScooter]:
        """Advance the simulation by `dt` seconds; returns scooters that must send telemetry."""
        due: list[SimScooter] = []
        for scooter in self.scooters:
            if scooter.phase is Phase.RIDING:
                self._ride(scooter, dt)
                due.append(scooter)
            elif scooter.phase is Phase.CHARGING:
                if scooter.charging_until is not None and now >= scooter.charging_until:
                    scooter.battery = self.rng.uniform(85.0, 100.0)
                    scooter.phase = Phase.IDLE
                    scooter.charging_until = None
                    scooter.idle_ticks = 0
                    due.append(scooter)
            else:
                scooter.idle_ticks += 1
                if scooter.idle_ticks >= self.config.heartbeat_ticks:
                    scooter.idle_ticks = 0
                    due.append(scooter)
        self._dispatch_rides(now)
        return due

    def _ride(self, scooter: SimScooter, dt: float) -> None:
        assert scooter.target is not None
        step_km = self.config.speed_kmh * dt / 3600
        lat, lon, reached = step_towards(scooter.lat, scooter.lon, *scooter.target, step_km)
        moved_km = haversine_km(scooter.lat, scooter.lon, lat, lon)
        scooter.lat, scooter.lon = lat, lon
        scooter.battery = max(0.0, scooter.battery - moved_km * self.config.drain_per_km)
        if reached or scooter.battery <= 0.0:
            scooter.phase = Phase.IDLE
            scooter.target = None

    def _dispatch_rides(self, now: float) -> None:
        riding = sum(scooter.phase is Phase.RIDING for scooter in self.scooters)
        needed = self.config.active_scooters - riding
        if needed <= 0:
            return
        candidates = [
            scooter
            for scooter in self.scooters
            if scooter.phase is Phase.IDLE
            and not scooter.parked
            and scooter.battery >= self.config.min_ride_battery
        ]
        for scooter in self.rng.sample(candidates, min(needed, len(candidates))):
            self.start_ride(scooter, random_point(BISHKEK_BBOX, self.rng), now)
