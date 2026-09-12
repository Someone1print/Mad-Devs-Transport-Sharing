import pytest

from scootersim.geo import (
    BISHKEK_BBOX,
    haversine_km,
    in_bbox,
    in_edge_band,
    inner_box,
    random_edge_point,
    random_point,
    step_towards,
)


def test_haversine_matches_known_distance() -> None:
    # Ala-Too Square -> Osh Bazaar is roughly 2.5 km west
    assert haversine_km(42.8756, 74.6036, 42.8747, 74.5731) == pytest.approx(2.49, abs=0.05)


def test_step_towards_moves_closer_without_overshooting() -> None:
    start, target = (42.8700, 74.5900), (42.8800, 74.6000)
    before = haversine_km(*start, *target)

    lat, lon, reached = step_towards(*start, *target, distance_km=0.2)

    assert not reached
    after = haversine_km(lat, lon, *target)
    assert after == pytest.approx(before - 0.2, abs=0.01)


def test_step_towards_snaps_to_target_when_close_enough() -> None:
    lat, lon, reached = step_towards(42.8700, 74.5900, 42.8701, 74.5901, distance_km=5.0)

    assert reached
    assert (lat, lon) == (42.8701, 74.5901)


def test_random_point_stays_inside_bbox() -> None:
    import random

    rng = random.Random(7)
    for _ in range(100):
        lat, lon = random_point(BISHKEK_BBOX, rng)
        assert BISHKEK_BBOX.min_lat <= lat <= BISHKEK_BBOX.max_lat
        assert BISHKEK_BBOX.min_lon <= lon <= BISHKEK_BBOX.max_lon


def test_inner_box_and_edge_band_partition_the_bbox() -> None:
    core = inner_box(BISHKEK_BBOX)

    assert core.min_lat > BISHKEK_BBOX.min_lat and core.max_lat < BISHKEK_BBOX.max_lat
    assert in_bbox((42.875, 74.600), core)
    assert not in_edge_band((42.875, 74.600), BISHKEK_BBOX)
    assert in_edge_band((42.856, 74.600), BISHKEK_BBOX)
    assert not in_edge_band((42.800, 74.600), BISHKEK_BBOX)  # outside the box altogether


def test_random_edge_point_lies_in_the_outer_band() -> None:
    import random

    rng = random.Random(11)
    for _ in range(200):
        assert in_edge_band(random_edge_point(BISHKEK_BBOX, rng), BISHKEK_BBOX)


def test_random_edge_point_near_a_position_picks_the_closest_side() -> None:
    import random

    rng = random.Random(3)
    core = inner_box(BISHKEK_BBOX)
    # just inside the core, close to its western side: the point must land in the western band
    lat, lon = (core.min_lat + core.max_lat) / 2, core.min_lon + 0.0005
    for _ in range(50):
        point = random_edge_point(BISHKEK_BBOX, rng, near=(lat, lon))
        assert in_edge_band(point, BISHKEK_BBOX)
        assert point[1] < core.min_lon
        assert (
            abs(point[0] - lat) <= 0.003
        )  # roughly opposite the rider, not anywhere along the side
