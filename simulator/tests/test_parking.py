import logging
import random
from typing import Any

from scootersim.config import Config
from scootersim.fleet import Fleet, Phase, SimScooter
from scootersim.runner import run
from tests.test_fleet import make_config


def make_fleet(scooters: list[SimScooter], **overrides: object) -> Fleet:
    return Fleet(scooters, make_config(**overrides), random.Random(3))


def test_reserved_scooter_does_not_start_rides() -> None:
    scooter = SimScooter("KG-1", 42.87, 74.59, battery=90.0)
    fleet = make_fleet([scooter], active_scooters=1)
    fleet.apply_server_status("KG-1", "reserved", now=0.0)

    fleet.tick(dt=1.0, now=1.0)

    assert scooter.phase is Phase.IDLE
    assert scooter.parked


def test_reserving_a_riding_scooter_stops_it_where_it_is() -> None:
    scooter = SimScooter("KG-1", 42.8700, 74.5900, battery=90.0)
    fleet = make_fleet([scooter], active_scooters=0)
    fleet.start_ride(scooter, target=(42.9000, 74.5900), now=0.0)
    fleet.tick(dt=1.0, now=1.0)
    position = (scooter.lat, scooter.lon)

    fleet.apply_server_status("KG-1", "reserved", now=1.0)
    fleet.tick(dt=1.0, now=2.0)

    assert scooter.phase is Phase.IDLE
    assert scooter.target is None
    assert (scooter.lat, scooter.lon) == position


def test_available_status_releases_a_parked_scooter() -> None:
    scooter = SimScooter("KG-1", 42.87, 74.59, battery=90.0)
    fleet = make_fleet([scooter], active_scooters=1)
    fleet.apply_server_status("KG-1", "reserved", now=0.0)

    fleet.apply_server_status("KG-1", "available", now=5.0)
    fleet.tick(dt=1.0, now=6.0)

    assert not scooter.parked
    assert scooter.phase is Phase.RIDING


def test_refresh_statuses_parks_scooters_reported_as_reserved() -> None:
    scooters = [SimScooter("KG-1", 42.87, 74.59, 90.0), SimScooter("KG-2", 42.88, 74.60, 90.0)]
    fleet = make_fleet(scooters, active_scooters=0)

    fleet.refresh_statuses(
        [
            {"code": "KG-1", "status": "reserved"},
            {"code": "KG-2", "status": "available"},
            {"code": "KG-9", "status": "available"},  # unknown codes are ignored
        ],
        now=0.0,
    )

    assert scooters[0].parked and not scooters[1].parked


class RecordingClient:
    def __init__(self, payloads: list[list[dict[str, Any]]]) -> None:
        self.payloads = payloads
        self.fetches = 0
        self.telemetry: list[str] = []

    def fetch_scooters(self) -> list[dict[str, Any]]:
        payload = self.payloads[min(self.fetches, len(self.payloads) - 1)]
        self.fetches += 1
        return payload

    def send_telemetry(self, code: str, lat: float, lon: float, battery: int) -> dict[str, Any]:
        self.telemetry.append(code)
        return {"code": code, "status": "available"}


def test_runner_refreshes_statuses_every_n_ticks() -> None:
    initial = [{"code": "KG-1", "lat": 42.87, "lon": 74.59, "battery": 90, "status": "available"}]
    later = [{"code": "KG-1", "lat": 42.87, "lon": 74.59, "battery": 90, "status": "reserved"}]
    client = RecordingClient([initial, later])
    config = Config(active_scooters=1, interval_seconds=1.0, refresh_every_ticks=3)

    run(
        config,
        client,
        sleep=lambda _: None,
        clock=lambda: 0.0,
        max_ticks=8,
        log=logging.getLogger("t"),
    )

    assert client.fetches >= 2  # initial load plus at least one periodic refresh
    # after the refresh reported "reserved" the scooter stopped riding: telemetry stops flowing
    assert len(client.telemetry) < 8
