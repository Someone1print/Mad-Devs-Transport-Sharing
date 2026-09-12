"""Scooters ridden by real users (status `riding`) are driven by the simulator too."""

import random

from scootersim.fleet import Fleet, Phase, SimScooter
from scootersim.geo import BISHKEK_BBOX, RIDE_BBOX, haversine_km
from tests.test_fleet import make_config


def make_fleet(scooters: list[SimScooter], **overrides: object) -> Fleet:
    return Fleet(scooters, make_config(**overrides), random.Random(5))


def test_ride_bbox_is_wider_than_the_demo_bbox() -> None:
    assert RIDE_BBOX.min_lat < BISHKEK_BBOX.min_lat
    assert RIDE_BBOX.max_lat > BISHKEK_BBOX.max_lat
    assert RIDE_BBOX.min_lon < BISHKEK_BBOX.min_lon
    assert RIDE_BBOX.max_lon > BISHKEK_BBOX.max_lon


def test_riding_status_makes_the_scooter_move_and_drain() -> None:
    scooter = SimScooter("KG-1", 42.8700, 74.5900, battery=80.0)
    fleet = make_fleet([scooter], active_scooters=0)

    fleet.apply_server_status("KG-1", "riding", now=0.0)
    due = fleet.tick(dt=1.0, now=1.0)

    assert scooter.phase is Phase.RIDING
    assert scooter.user_ride is True
    assert (scooter.lat, scooter.lon) != (42.8700, 74.5900)
    assert scooter.battery < 80.0
    assert scooter in due


def test_user_ride_keeps_going_after_reaching_its_target() -> None:
    scooter = SimScooter("KG-1", 42.8700, 74.5900, battery=80.0)
    fleet = make_fleet([scooter], active_scooters=0, speed_kmh=36.0)
    fleet.apply_server_status("KG-1", "riding", now=0.0)
    scooter.target = (42.87005, 74.5900)  # ~5 m away: reached on the first tick

    fleet.tick(dt=1.0, now=1.0)
    first_target = scooter.target
    fleet.tick(dt=1.0, now=2.0)

    assert scooter.phase is Phase.RIDING
    assert first_target is not None and first_target != (42.87005, 74.5900)
    assert RIDE_BBOX.min_lat <= first_target[0] <= RIDE_BBOX.max_lat
    assert RIDE_BBOX.min_lon <= first_target[1] <= RIDE_BBOX.max_lon


def test_paused_user_ride_stands_still() -> None:
    scooter = SimScooter("KG-1", 42.8700, 74.5900, battery=80.0)
    fleet = make_fleet([scooter], active_scooters=0)
    fleet.apply_server_status("KG-1", "riding", now=0.0)
    fleet.tick(dt=1.0, now=1.0)
    position = (scooter.lat, scooter.lon)

    fleet.apply_server_status("KG-1", "riding", now=2.0, paused=True)
    fleet.tick(dt=1.0, now=3.0)

    assert (scooter.lat, scooter.lon) == position
    assert scooter.phase is Phase.IDLE and scooter.parked

    fleet.apply_server_status("KG-1", "riding", now=4.0, paused=False)
    fleet.tick(dt=1.0, now=5.0)

    assert scooter.phase is Phase.RIDING
    assert (scooter.lat, scooter.lon) != position


def test_user_ride_ends_when_the_backend_frees_the_scooter() -> None:
    scooter = SimScooter("KG-1", 42.8700, 74.5900, battery=80.0)
    fleet = make_fleet([scooter], active_scooters=0)
    fleet.apply_server_status("KG-1", "riding", now=0.0)
    fleet.tick(dt=1.0, now=1.0)

    fleet.apply_server_status("KG-1", "available", now=2.0)
    fleet.tick(dt=1.0, now=3.0)

    assert scooter.phase is Phase.IDLE
    assert scooter.user_ride is False and not scooter.parked


def test_user_rides_do_not_count_towards_the_demo_quota() -> None:
    user_scooter = SimScooter("KG-1", 42.87, 74.59, battery=90.0)
    demo = [SimScooter(f"KG-{i}", 42.87, 74.59, battery=90.0) for i in range(2, 5)]
    fleet = make_fleet([user_scooter, *demo], active_scooters=2)
    fleet.apply_server_status("KG-1", "riding", now=0.0)

    fleet.tick(dt=1.0, now=1.0)

    assert sum(s.phase is Phase.RIDING and not s.user_ride for s in demo) == 2


def test_refresh_reads_the_paused_flag() -> None:
    scooter = SimScooter("KG-1", 42.87, 74.59, battery=90.0)
    fleet = make_fleet([scooter], active_scooters=0)

    fleet.refresh_statuses([{"code": "KG-1", "status": "riding", "paused": True}], now=0.0)

    assert scooter.parked and scooter.phase is Phase.IDLE


def test_flat_battery_stops_a_user_ride_locally() -> None:
    scooter = SimScooter("KG-1", 42.8700, 74.5900, battery=0.02)
    fleet = make_fleet([scooter], active_scooters=0)
    fleet.apply_server_status("KG-1", "riding", now=0.0)

    fleet.tick(dt=1.0, now=1.0)
    moved = haversine_km(42.8700, 74.5900, scooter.lat, scooter.lon)

    assert scooter.battery == 0.0
    assert scooter.phase is Phase.IDLE
    assert moved > 0
