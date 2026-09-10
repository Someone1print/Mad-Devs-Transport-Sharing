import pytest

from scootersim.geo import BISHKEK_BBOX, haversine_km, random_point, step_towards


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
