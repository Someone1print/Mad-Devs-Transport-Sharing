"""Scooters ridden by real users (status `riding`) are driven by the simulator too — inside
the service zone only: the rider decides where to go, and a demo rider never leaves the zone."""

import random

from scootersim.fleet import FALLBACK_RIDE_AREA, Fleet, Phase, SimScooter
from scootersim.geo import haversine_km, point_in_polygon
from tests.test_fleet import make_config

# the backend's service zone (backend/app/zones.py), as GET /api/zones returns it
ZONE = [
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
ZONES_PAYLOAD = [
    {"id": 1, "name": "Центр", "points": [{"lat": lat, "lon": lon} for lat, lon in ZONE]}
]


def make_fleet(scooters: list[SimScooter], **overrides: object) -> Fleet:
    return Fleet(scooters, make_config(**overrides), random.Random(5), zones=[ZONE])


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


def test_user_ride_targets_lie_inside_the_service_zone() -> None:
    scooter = SimScooter("KG-1", 42.8700, 74.5900, battery=80.0)
    fleet = make_fleet([scooter], active_scooters=0)
    fleet.apply_server_status("KG-1", "riding", now=0.0)
    targets = [scooter.target]
    for _ in range(20):
        scooter.lat, scooter.lon = scooter.target  # teleport: reached, the rider drives on
        fleet.tick(dt=1.0, now=1.0)
        targets.append(scooter.target)

    assert scooter.phase is Phase.RIDING
    assert len(set(targets)) == len(targets)
    assert all(point_in_polygon(t, ZONE) for t in targets)


def test_user_ride_never_leaves_the_zone_and_turns_around_at_the_border() -> None:
    """Even with a target outside (a stale one, or a concave zone), the scooter stays inside:
    the step that would cross the border is not taken and a new target inside is chosen."""
    scooter = SimScooter("KG-1", 42.8730, 74.5790, battery=80.0)  # ~120 m inside the west edge
    fleet = make_fleet([scooter], active_scooters=0, speed_kmh=36.0)  # 10 m per tick
    fleet.apply_server_status("KG-1", "riding", now=0.0)
    outside = (42.8730, 74.5700)
    scooter.target = outside

    for tick in range(1, 60):
        fleet.tick(dt=1.0, now=float(tick))
        assert point_in_polygon((scooter.lat, scooter.lon), ZONE), f"left the zone at tick {tick}"

    assert scooter.phase is Phase.RIDING
    assert scooter.target != outside and point_in_polygon(scooter.target, ZONE)


def test_a_scooter_taken_outside_the_zone_drives_in() -> None:
    scooter = SimScooter("KG-2", 42.8747, 74.5731, battery=80.0)  # Osh Bazaar, west of the zone
    fleet = make_fleet([scooter], active_scooters=0, speed_kmh=36.0)
    fleet.apply_server_status("KG-2", "riding", now=0.0)

    assert point_in_polygon(scooter.target, ZONE)
    for tick in range(1, 120):  # 1.2 km at 10 m per tick
        fleet.tick(dt=1.0, now=float(tick))
        if point_in_polygon((scooter.lat, scooter.lon), ZONE):
            break
    else:
        raise AssertionError("never entered the zone")
    assert scooter.phase is Phase.RIDING


def test_zones_come_from_the_backend_payload() -> None:
    fleet = Fleet.from_server(
        [{"code": "KG-1", "lat": 42.87, "lon": 74.59, "battery": 80, "status": "riding"}],
        make_config(active_scooters=0),
        random.Random(1),
        now=0.0,
        zones=ZONES_PAYLOAD,
    )

    assert fleet.zones == [ZONE]
    assert point_in_polygon(fleet.scooters[0].target, ZONE)


def test_without_zones_user_rides_stay_in_the_central_fallback_area() -> None:
    scooter = SimScooter("KG-1", 42.8700, 74.5900, battery=80.0)
    fleet = Fleet([scooter], make_config(active_scooters=0), random.Random(5), zones=[])
    fleet.apply_server_status("KG-1", "riding", now=0.0)

    assert fleet.zones == [FALLBACK_RIDE_AREA]
    assert point_in_polygon(scooter.target, FALLBACK_RIDE_AREA)


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
    assert point_in_polygon(next_target, ZONE)


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


def test_available_reply_does_not_abort_a_demo_ride() -> None:
    """A demo-riding scooter is `available` on the server; every telemetry reply says so."""
    scooter = SimScooter("KG-1", 42.8700, 74.5900, battery=90.0)
    fleet = make_fleet([scooter], active_scooters=1)
    fleet.tick(dt=1.0, now=1.0)  # dispatched as a demo ride
    assert scooter.phase is Phase.RIDING
    target = scooter.target

    fleet.apply_server_status("KG-1", "available", now=1.5)
    fleet.tick(dt=1.0, now=2.0)

    assert scooter.phase is Phase.RIDING
    assert scooter.target == target


def test_resume_continues_the_interrupted_leg() -> None:
    scooter = SimScooter("KG-1", 42.8700, 74.5900, battery=90.0)
    fleet = make_fleet([scooter], active_scooters=0)
    fleet.apply_server_status("KG-1", "riding", now=0.0)
    target = scooter.target

    fleet.apply_server_status("KG-1", "riding", now=1.0, paused=True)
    fleet.apply_server_status("KG-1", "riding", now=2.0, paused=False)

    assert scooter.phase is Phase.RIDING
    assert scooter.target == target


def test_riding_received_mid_demo_ride_starts_a_user_ride_inside_the_zone() -> None:
    scooter = SimScooter("KG-1", 42.8700, 74.5900, battery=90.0)
    fleet = make_fleet([scooter], active_scooters=1)
    fleet.tick(dt=1.0, now=1.0)  # demo ride with a target anywhere in the city box
    demo_target = scooter.target

    fleet.apply_server_status("KG-1", "riding", now=2.0)

    assert scooter.user_ride
    assert scooter.target != demo_target and point_in_polygon(scooter.target, ZONE)
