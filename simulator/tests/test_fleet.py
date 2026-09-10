import random

import pytest

from scootersim.config import Config
from scootersim.fleet import Fleet, Phase, SimScooter


def make_config(**overrides: object) -> Config:
    values: dict[str, object] = {
        "backend_url": "http://backend:8000",
        "active_scooters": 2,
        "interval_seconds": 1.0,
        "speed_kmh": 36.0,  # 10 m per second
        "drain_per_km": 10.0,
        "recharge_seconds": 30.0,
        "min_ride_battery": 20,
        "heartbeat_ticks": 5,
    }
    values.update(overrides)
    return Config(**values)  # type: ignore[arg-type]


def make_fleet(scooters: list[SimScooter], **overrides: object) -> Fleet:
    return Fleet(scooters, make_config(**overrides), random.Random(1))


def test_riding_scooter_moves_and_drains_battery() -> None:
    scooter = SimScooter("KG-1", 42.8700, 74.5900, battery=50.0)
    fleet = make_fleet([scooter], active_scooters=0)
    fleet.start_ride(scooter, target=(42.8900, 74.5900), now=0.0)

    due = fleet.tick(dt=1.0, now=1.0)

    assert scooter.phase is Phase.RIDING
    assert scooter.lat > 42.8700  # moved north towards the target
    assert scooter.battery == pytest.approx(50.0 - 10.0 * 0.01, abs=0.001)  # 10 m at 10 %/km
    assert scooter in due


def test_ride_ends_when_target_is_reached() -> None:
    scooter = SimScooter("KG-1", 42.8700, 74.5900, battery=50.0)
    fleet = make_fleet([scooter], active_scooters=0)
    fleet.start_ride(scooter, target=(42.87005, 74.5900), now=0.0)  # ~5 m away

    fleet.tick(dt=1.0, now=1.0)

    assert scooter.phase is Phase.IDLE
    assert (scooter.lat, scooter.lon) == (42.87005, 74.5900)


def test_idle_scooters_start_rides_up_to_active_count() -> None:
    scooters = [SimScooter(f"KG-{i}", 42.87, 74.59, battery=90.0) for i in range(5)]
    fleet = make_fleet(scooters, active_scooters=2)

    fleet.tick(dt=1.0, now=1.0)

    assert sum(s.phase is Phase.RIDING for s in scooters) == 2


def test_low_battery_scooter_does_not_start_riding() -> None:
    scooters = [SimScooter("KG-1", 42.87, 74.59, battery=10.0)]
    fleet = make_fleet(scooters, active_scooters=1, min_ride_battery=20)

    fleet.tick(dt=1.0, now=1.0)

    assert scooters[0].phase is Phase.IDLE


def test_ride_stops_when_battery_runs_out() -> None:
    scooter = SimScooter("KG-1", 42.8700, 74.5900, battery=0.05)
    fleet = make_fleet([scooter], active_scooters=0)
    fleet.start_ride(scooter, target=(42.9000, 74.5900), now=0.0)

    fleet.tick(dt=1.0, now=1.0)

    assert scooter.phase is Phase.IDLE
    assert scooter.battery == 0.0


def test_unavailable_scooter_is_recharged_after_timeout() -> None:
    scooter = SimScooter("KG-1", 42.87, 74.59, battery=5.0)
    fleet = make_fleet([scooter], active_scooters=0, recharge_seconds=30.0)

    fleet.apply_server_status(scooter.code, "unavailable", now=0.0)
    assert scooter.phase is Phase.CHARGING
    assert scooter not in fleet.tick(dt=1.0, now=10.0)

    due = fleet.tick(dt=1.0, now=31.0)

    assert scooter.phase is Phase.IDLE
    assert scooter.battery >= 85.0
    assert scooter in due


def test_idle_scooters_report_heartbeat_periodically() -> None:
    scooter = SimScooter("KG-1", 42.87, 74.59, battery=90.0)
    fleet = make_fleet([scooter], active_scooters=0, heartbeat_ticks=3)

    reports = [scooter in fleet.tick(dt=1.0, now=float(t)) for t in range(1, 7)]

    assert reports == [False, False, True, False, False, True]


def test_fleet_from_server_reads_backend_payload() -> None:
    payload = [
        {"code": "KG-1", "lat": 42.87, "lon": 74.59, "battery": 80, "status": "available"},
        {"code": "KG-2", "lat": 42.88, "lon": 74.60, "battery": 9, "status": "unavailable"},
    ]

    fleet = Fleet.from_server(payload, make_config(), random.Random(1), now=0.0)

    assert [s.code for s in fleet.scooters] == ["KG-1", "KG-2"]
    assert fleet.scooters[0].phase is Phase.IDLE
    assert fleet.scooters[1].phase is Phase.CHARGING
