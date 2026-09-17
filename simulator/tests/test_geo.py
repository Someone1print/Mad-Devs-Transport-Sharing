import random

import pytest

from scootersim.geo import (
    BISHKEK_BBOX,
    bbox_polygon,
    haversine_km,
    in_bbox,
    inner_box,
    point_in_polygon,
    random_point,
    random_point_in_polygon,
    step_towards,
)

SQUARE = [(0.0, 0.0), (0.0, 10.0), (10.0, 10.0), (10.0, 0.0)]
# a U shape: the notch (lat 4..6, lon 5..10) lies outside
CONCAVE = [
    (0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (6.0, 10.0),
    (6.0, 5.0), (4.0, 5.0), (4.0, 10.0), (0.0, 10.0),
]  # fmt: skip


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
    rng = random.Random(7)
    for _ in range(100):
        lat, lon = random_point(BISHKEK_BBOX, rng)
        assert BISHKEK_BBOX.min_lat <= lat <= BISHKEK_BBOX.max_lat
        assert BISHKEK_BBOX.min_lon <= lon <= BISHKEK_BBOX.max_lon


def test_inner_box_shrinks_every_side() -> None:
    core = inner_box(BISHKEK_BBOX, 0.3)

    assert core.min_lat > BISHKEK_BBOX.min_lat and core.max_lat < BISHKEK_BBOX.max_lat
    assert core.min_lon > BISHKEK_BBOX.min_lon and core.max_lon < BISHKEK_BBOX.max_lon
    assert in_bbox((42.875, 74.600), core)
    assert not in_bbox((42.856, 74.600), core)


def test_point_in_polygon_square_and_concave_shape() -> None:
    assert point_in_polygon((5.0, 5.0), SQUARE)
    assert not point_in_polygon((5.0, 10.5), SQUARE)
    assert not point_in_polygon((-1.0, 5.0), SQUARE)
    assert point_in_polygon((2.0, 7.0), CONCAVE)
    assert not point_in_polygon((5.0, 7.0), CONCAVE)  # in the notch
    assert not point_in_polygon((5.0, 5.0), [(0.0, 0.0), (1.0, 1.0)])  # degenerate: nothing inside


def test_random_point_in_polygon_lands_inside_even_for_a_concave_shape() -> None:
    rng = random.Random(11)
    for _ in range(300):
        assert point_in_polygon(random_point_in_polygon(CONCAVE, rng), CONCAVE)


def test_bbox_polygon_is_the_box_as_a_ring() -> None:
    ring = bbox_polygon(BISHKEK_BBOX)

    assert len(ring) == 4
    assert point_in_polygon((42.875, 74.600), ring)
    assert not point_in_polygon((42.800, 74.600), ring)
