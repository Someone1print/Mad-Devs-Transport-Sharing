"""Scooters ridden by real users (status `riding`) are driven by the simulator too."""

import random

from scootersim.fleet import Fleet, Phase, SimScooter
from scootersim.geo import (
    BISHKEK_BBOX,
    DEEP_CORE_SHARE,
    RIDE_BBOX,
    haversine_km,
    in_bbox,
    in_edge_band,
    inner_box,
)
from tests.test_fleet import make_config


def make_fleet(scooters: list[SimScooter], **overrides: object) -> Fleet:
    return Fleet(scooters, make_config(**overrides), random.Random(5))


# the backend's service zone (backend/app/zones.py), for the "slightly wider" check below
ZONE_MIN_LAT, ZONE_MAX_LAT, ZONE_MIN_LON, ZONE_MAX_LON = 42.8615, 42.8885, 74.5775, 74.6225


def test_ride_bbox_is_slightly_wider_than_the_service_zone() -> None:
    assert RIDE_BBOX.min_lat < ZONE_MIN_LAT and RIDE_BBOX.max_lat > ZONE_MAX_LAT
    assert RIDE_BBOX.min_lon < ZONE_MIN_LON and RIDE_BBOX.max_lon > ZONE_MAX_LON
    # ...but not by much: at most ~0.8 km beyond the zone on any side
    assert ZONE_MIN_LAT - RIDE_BBOX.min_lat < 0.008 and RIDE_BBOX.max_lat - ZONE_MAX_LAT < 0.008
    assert ZONE_MIN_LON - RIDE_BBOX.min_lon < 0.010 and RIDE_BBOX.max_lon - ZONE_MAX_LON < 0.010
    assert BISHKEK_BBOX.min_lat <= RIDE_BBOX.min_lat  # demo rides stay in the old, larger box


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
    next_target = scooter.target
    fleet.tick(dt=1.0, now=2.0)

    assert scooter.phase is Phase.RIDING
    assert next_target is not None and next_target != (42.87005, 74.5900)
    assert in_bbox(next_target, RIDE_BBOX)


def test_user_ride_targets_alternate_between_the_edge_and_the_core() -> None:
    """Demo determinism: the first leg heads for the edge of the riding area (outside the
    service zone), the next one for the core (inside), and so on."""
    scooter = SimScooter("KG-1", 42.8700, 74.5900, battery=80.0)
    fleet = make_fleet([scooter], active_scooters=0)
    fleet.apply_server_status("KG-1", "riding", now=0.0)
    targets = [scooter.target]
    for _ in range(3):
        scooter.lat, scooter.lon = scooter.target  # teleport: reached
        fleet.tick(dt=1.0, now=1.0)
        targets.append(scooter.target)

    assert [in_edge_band(t, RIDE_BBOX) for t in targets] == [True, False, True, False]
    deep = inner_box(RIDE_BBOX, DEEP_CORE_SHARE)
    assert [in_bbox(t, deep) for t in targets] == [False, True, False, True]


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


def test_held_scooters_report_often_so_status_changes_are_seen_quickly() -> None:
    """A reserved or paused scooter is about to change state (ride start / resume): it reports
    every `held_heartbeat_ticks` ticks instead of the idle heartbeat, so the simulator learns the
    new status from the telemetry response within a few seconds."""
    reserved = SimScooter("KG-1", 42.87, 74.59, battery=90.0)
    paused = SimScooter("KG-2", 42.87, 74.59, battery=90.0)
    idle = SimScooter("KG-3", 42.87, 74.59, battery=90.0)
    fleet = make_fleet(
        [reserved, paused, idle], active_scooters=0, heartbeat_ticks=20, held_heartbeat_ticks=2
    )
    fleet.apply_server_status("KG-1", "reserved", now=0.0)
    fleet.apply_server_status("KG-2", "riding", now=0.0, paused=True)

    reports = [[s.code for s in fleet.tick(dt=1.0, now=float(t))] for t in range(1, 5)]

    assert reports == [[], ["KG-1", "KG-2"], [], ["KG-1", "KG-2"]]


def test_deep_core_lies_inside_the_service_zone_with_a_margin() -> None:
    """The backend's zone polygon (backend/app/zones.py) must contain the deep core, or return
    legs would not bring the ride back inside. Checked with the same even-odd rule."""
    zone = [
        (42.8880, 74.5900),
        (42.8885, 74.6060),
        (42.8860, 74.6200),
        (42.8790, 74.6225),
        (42.8700, 74.6215),
        (42.8630, 74.6120),
        (42.8615, 74.5950),
        (42.8640, 74.5800),
        (42.8730, 74.5775),
        (42.8830, 74.5790),
    ]

    def inside(lat: float, lon: float) -> bool:
        inn = False
        for i, (a_lat, a_lon) in enumerate(zone):
            b_lat, b_lon = zone[(i + 1) % len(zone)]
            if (a_lon > lon) != (b_lon > lon):
                edge_lat = a_lat + (lon - a_lon) * (b_lat - a_lat) / (b_lon - a_lon)
                if lat < edge_lat:
                    inn = not inn
        return inn

    deep = inner_box(RIDE_BBOX, DEEP_CORE_SHARE)
    corners = [
        (deep.min_lat, deep.min_lon),
        (deep.min_lat, deep.max_lon),
        (deep.max_lat, deep.min_lon),
        (deep.max_lat, deep.max_lon),
    ]
    assert all(inside(lat, lon) for lat, lon in corners)
