import random
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from scootersim.config import Config
from scootersim.geo import (
    BISHKEK_BBOX,
    Point,
    Polygon,
    bbox_polygon,
    haversine_km,
    inner_box,
    point_in_polygon,
    random_point,
    random_point_in_polygon,
    step_towards,
)

# Where a user ride wanders when the backend has no service zone at all: the central 40 % of
# the city box. Finishing is impossible without a zone anyway; the demo just keeps moving.
FALLBACK_RIDE_AREA: Polygon = bbox_polygon(inner_box(BISHKEK_BBOX, 0.3))


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
    user_ride_started: bool = False  # the demo target was dropped for the current user ride

    @property
    def battery_percent(self) -> int:
        return max(0, min(100, round(self.battery)))


class Fleet:
    """Local state of the simulated scooters; `tick` advances it and says who must report.

    `zones` are the backend's service zones: a user ride never leaves the zone it is in (the
    rider, not the simulator, decides where to go — and a demo rider stays where finishing is
    allowed). Demo rides of free scooters roam the whole city box.
    """

    def __init__(
        self,
        scooters: Iterable[SimScooter],
        config: Config,
        rng: random.Random,
        zones: list[Polygon] | None = None,
    ) -> None:
        self.scooters = list(scooters)
        self.config = config
        self.rng = rng
        self.zones: list[Polygon] = [list(zone) for zone in zones or []] or [FALLBACK_RIDE_AREA]
        self._by_code = {scooter.code: scooter for scooter in self.scooters}

    @classmethod
    def from_server(
        cls,
        payload: list[dict[str, Any]],
        config: Config,
        rng: random.Random,
        now: float,
        zones: list[dict[str, Any]] | None = None,
    ) -> "Fleet":
        """Build the fleet from GET /api/scooters and the zones from GET /api/zones."""
        scooters = [
            SimScooter(item["code"], item["lat"], item["lon"], float(item["battery"]))
            for item in payload
        ]
        polygons = [
            [(float(p["lat"]), float(p["lon"])) for p in zone.get("points", [])]
            for zone in zones or []
        ]
        fleet = cls(scooters, config, rng, zones=[z for z in polygons if len(z) >= 3])
        fleet.refresh_statuses(payload, now)
        return fleet

    def start_ride(self, scooter: SimScooter, target: tuple[float, float], now: float) -> None:
        del now  # rides do not depend on wall-clock time yet
        scooter.phase = Phase.RIDING
        scooter.target = target
        scooter.idle_ticks = 0

    def _zone_of(self, point: Point) -> Polygon | None:
        return next((zone for zone in self.zones if point_in_polygon(point, zone)), None)

    def _next_user_target(self, scooter: SimScooter) -> Point:
        """A random point inside the zone the rider is in; a rider outside every zone (a scooter
        taken from a spot outside, or a stale position) heads into the first one."""
        zone = self._zone_of((scooter.lat, scooter.lon)) or self.zones[0]
        return random_point_in_polygon(zone, self.rng)

    def _leaves_zone(self, scooter: SimScooter, new_position: Point) -> bool:
        """Would this step take a rider who is inside a zone out of it?"""
        zone = self._zone_of((scooter.lat, scooter.lon))
        return zone is not None and not point_in_polygon(new_position, zone)

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
            # a real user drives it inside the service zone; a pause keeps the current leg
            was_user_ride = scooter.user_ride_started
            scooter.user_ride, scooter.user_ride_started = True, True
            scooter.parked = paused
            if not was_user_ride:
                scooter.target = None  # a demo target may lie outside the zone
            if paused:
                scooter.phase = Phase.IDLE
                scooter.idle_ticks = 0
            elif (scooter.phase is not Phase.RIDING or scooter.target is None) and (
                scooter.battery > 0.0
            ):
                target = scooter.target or self._next_user_target(scooter)
                self.start_ride(scooter, target, now)
        elif status == "available":
            if scooter.user_ride:
                # the user's ride ended: its target lies in the ride area, drop it
                self._stop(scooter)
            scooter.parked = scooter.user_ride = scooter.user_ride_started = False

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
        if scooter.user_ride and self._leaves_zone(scooter, (lat, lon)):
            # the rider turns around at the border: no step this tick, a new target inside
            scooter.target = self._next_user_target(scooter)
            return
        moved_km = haversine_km(scooter.lat, scooter.lon, lat, lon)
        scooter.lat, scooter.lon = lat, lon
        drain = moved_km * self.config.drain_per_km
        if scooter.user_ride:
            drain += self.config.user_ride_drain_per_minute * dt / 60
        scooter.battery = max(0.0, scooter.battery - drain)
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
