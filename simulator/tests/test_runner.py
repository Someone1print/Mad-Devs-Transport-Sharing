import logging
from typing import Any

import httpx

from scootersim.config import Config
from scootersim.runner import run

PAYLOAD = [
    {"code": "KG-1", "lat": 42.87, "lon": 74.59, "battery": 80, "status": "available"},
    {"code": "KG-2", "lat": 42.88, "lon": 74.60, "battery": 60, "status": "available"},
]


ZONE = [(42.86, 74.58), (42.86, 74.62), (42.89, 74.62), (42.89, 74.58)]
ZONES = [{"id": 1, "name": "Центр", "points": [{"lat": lat, "lon": lon} for lat, lon in ZONE]}]


class FlakyClient:
    """Backend that is down for the first N calls, then answers normally."""

    def __init__(self, failures: int, payload: list[dict[str, Any]] = PAYLOAD) -> None:
        self.failures = failures
        self.payload = payload
        self.calls = 0
        self.zone_calls = 0
        self.telemetry: list[dict[str, Any]] = []

    def fetch_scooters(self) -> list[dict[str, Any]]:
        self.calls += 1
        if self.calls <= self.failures:
            raise httpx.ConnectError("connection refused")
        return self.payload

    def fetch_zones(self) -> list[dict[str, Any]]:
        self.zone_calls += 1
        return ZONES

    def send_telemetry(self, code: str, lat: float, lon: float, battery: int) -> dict[str, Any]:
        self.telemetry.append({"code": code, "lat": lat, "lon": lon, "battery": battery})
        return {"code": code, "status": "available"}


def test_runner_survives_backend_outage_and_backs_off() -> None:
    client = FlakyClient(failures=2)
    sleeps: list[float] = []
    config = Config(active_scooters=2, interval_seconds=1.0, refresh_every_ticks=0)  # no refresh

    run(
        config,
        client,
        sleep=sleeps.append,
        clock=lambda: 0.0,
        max_ticks=5,
        log=logging.getLogger("test"),
    )

    assert client.calls == 3  # two failures, then the fleet loads
    assert sleeps[:2] == [1.0, 2.0]  # exponential backoff while the backend is down
    assert client.telemetry, "telemetry is sent once the backend is back"
    assert {t["code"] for t in client.telemetry} == {"KG-1", "KG-2"}
    assert all(0 <= t["battery"] <= 100 for t in client.telemetry)


def test_runner_loads_the_service_zones_once_and_keeps_user_rides_inside() -> None:
    riding = [{"code": "KG-1", "lat": 42.87, "lon": 74.60, "battery": 80, "status": "riding"}]
    client = FlakyClient(failures=0, payload=riding)
    config = Config(active_scooters=0, interval_seconds=1.0, refresh_every_ticks=0)

    run(config, client, sleep=lambda _: None, clock=lambda: 0.0, max_ticks=200)

    assert client.zone_calls == 1
    assert client.telemetry
    assert all(
        ZONE[0][0] <= t["lat"] <= ZONE[2][0] and ZONE[0][1] <= t["lon"] <= ZONE[2][1]
        for t in client.telemetry
    )
