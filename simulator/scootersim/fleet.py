import random
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from scootersim.config import Config
from scootersim.geo import (
    BISHKEK_BBOX,
    DEEP_CORE_SHARE,
    RIDE_BBOX,
    haversine_km,
    inner_box,
    random_edge_point,
    random_point,
    random_point_near,
    step_towards,
)


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
    parked: bool = False  # reserved, or a paused user ride: never moved by the simulator
    user_ride: bool = False  # a real user is riding it: keeps moving until the backend frees it
    legs: int = 0  # legs driven in the current user ride (targets alternate edge / core)
    user_ride_started: bool = False  # the leg counter was reset for the current user ride

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
        fleet.refresh_statuses(payload, now)
        return fleet

    def start_ride(self, scooter: SimScooter, target: tuple[float, float], now: float) -> None:
        del now  # rides do not depend on wall-clock time yet
        scooter.phase = Phase.RIDING
        scooter.target = target
        scooter.idle_ticks = 0

    def _next_user_target(self, scooter: SimScooter) -> tuple[float, float]:
        """User rides alternate between the edge of the riding area (outside the service zone)
        and its core (inside), so a demo can show both "finish refused" and "finish ok" within
        a few minutes instead of waiting for random targets to cross the boundary."""
        scooter.legs += 1
        position = (scooter.lat, scooter.lon)
        if scooter.legs % 2 == 1:
            return random_edge_point(RIDE_BBOX, self.rng, near=position)
        # back well inside the zone by the shortest way (the deep core lies inside the zone
        # with a margin, so the ride does not hover on the boundary)
        return random_point_near(inner_box(RIDE_BBOX, DEEP_CORE_SHARE), self.rng, near=position)

    def _stop(self, scooter: SimScooter) -> None:
        if scooter.phase is Phase.RIDING:
            scooter.phase = Phase.IDLE
            scooter.target = None

    def apply_server_status(self, code: str, status: str, now: float, paused: bool = False) -> None:
        """React to the status the backend reports back after telemetry or in the list."""
        scooter = self._by_code.get(code)
        if scooter is None:
            return
        if status == "unavailable":
            scooter.parked = scooter.user_ride = scooter.user_ride_started = False
            if scooter.phase is not Phase.CHARGING:
                scooter.phase = Phase.CHARGING
                scooter.target = None
                scooter.charging_until = now + self.config.recharge_seconds
        elif status == "reserved":
            # someone holds the scooter: it stays where it is until the backend frees it
            scooter.parked, scooter.user_ride, scooter.user_ride_started = True, False, False
            self._stop(scooter)
        elif status == "riding":
            # a real user drives it: it keeps moving (inside the wider ride area) unless paused
            scooter.user_ride = True
            scooter.parked = paused
            if paused:
                self._stop(scooter)
            elif scooter.phase is not Phase.RIDING and scooter.battery > 0.0:
                if not scooter.user_ride_started:
                    scooter.legs = 0
                    scooter.user_ride_started = True
                self.start_ride(scooter, self._next_user_target(scooter), now)
        elif status == "available":
            scooter.parked = scooter.user_ride = scooter.user_ride_started = False
            if scooter.phase is Phase.RIDING and scooter.target is not None:
                # the user's ride ended: the demo target lies in the wider area, drop it
                self._stop(scooter)

    def refresh_statuses(self, payload: list[dict[str, Any]], now: float) -> None:
        """Apply statuses from a fresh GET /api/scooters; unknown codes are ignored."""
        for item in payload:
            self.apply_server_status(
                str(item.get("code", "")),
                str(item.get("status", "")),
                now,
                paused=bool(item.get("paused", False)),
            )

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
                # a held scooter (reserved, or a paused user ride) is about to change state:
                # report often so the new status arrives in the next telemetry response
                heartbeat = (
                    self.config.held_heartbeat_ticks
                    if scooter.parked
                    else self.config.heartbeat_ticks
                )
                if scooter.idle_ticks >= heartbeat:
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
        if scooter.battery <= 0.0:
            self._stop(scooter)
        elif reached:
            if scooter.user_ride:
                scooter.target = self._next_user_target(scooter)  # the user drives on
            else:
                self._stop(scooter)

    def _dispatch_rides(self, now: float) -> None:
        riding = sum(s.phase is Phase.RIDING and not s.user_ride for s in self.scooters)
        needed = self.config.active_scooters - riding
        if needed <= 0:
            return
        candidates = [
            scooter
            for scooter in self.scooters
            if scooter.phase is Phase.IDLE
            and not scooter.parked
            and not scooter.user_ride
            and scooter.battery >= self.config.min_ride_battery
        ]
        for scooter in self.rng.sample(candidates, min(needed, len(candidates))):
            self.start_ride(scooter, random_point(BISHKEK_BBOX, self.rng), now)
