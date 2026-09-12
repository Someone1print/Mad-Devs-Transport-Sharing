import math
import random
from dataclasses import dataclass

EARTH_RADIUS_KM = 6371.0088


@dataclass(frozen=True)
class BBox:
    min_lat: float
    max_lat: float
    min_lon: float
    max_lon: float


# Central Bishkek: roughly 4.5 km north-south by 5.7 km east-west
BISHKEK_BBOX = BBox(min_lat=42.855, max_lat=42.895, min_lon=74.565, max_lon=74.635)

# Where user rides may wander: about half a kilometre beyond the backend's service zone on
# every side (the zone covers ~45 % of this box), so a ride regularly crosses the boundary and
# the "finish only inside the zone" rule can be demonstrated within a couple of minutes.
RIDE_BBOX = BBox(min_lat=42.856, max_lat=42.894, min_lon=74.570, max_lon=74.630)


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two points in kilometres."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def step_towards(
    lat: float, lon: float, target_lat: float, target_lon: float, distance_km: float
) -> tuple[float, float, bool]:
    """Move `distance_km` towards the target along a straight line.

    Returns the new position and whether the target was reached (then the position is exactly
    the target). Linear interpolation in degrees is accurate enough at city scale.
    """
    remaining = haversine_km(lat, lon, target_lat, target_lon)
    if remaining <= distance_km:
        return target_lat, target_lon, True
    fraction = distance_km / remaining
    return lat + (target_lat - lat) * fraction, lon + (target_lon - lon) * fraction, False


def random_point(bbox: BBox, rng: random.Random) -> tuple[float, float]:
    return rng.uniform(bbox.min_lat, bbox.max_lat), rng.uniform(bbox.min_lon, bbox.max_lon)


def random_point_near(
    bbox: BBox, rng: random.Random, near: tuple[float, float], jitter: float = 0.004
) -> tuple[float, float]:
    """A point of the box close to `near`: `near` clamped into the box, then jittered."""
    lat = min(bbox.max_lat, max(bbox.min_lat, near[0]))
    lon = min(bbox.max_lon, max(bbox.min_lon, near[1]))
    lat = min(bbox.max_lat, max(bbox.min_lat, lat + rng.uniform(-jitter, jitter)))
    lon = min(bbox.max_lon, max(bbox.min_lon, lon + rng.uniform(-jitter, jitter)))
    return lat, lon


def in_bbox(point: tuple[float, float], bbox: BBox) -> bool:
    lat, lon = point
    return bbox.min_lat <= lat <= bbox.max_lat and bbox.min_lon <= lon <= bbox.max_lon


# Share of the box (per side) that counts as its edge; the rest is the core.
EDGE_SHARE = 0.15
# Return legs of user rides aim deeper: the central part that lies well inside the service
# zone (about half a kilometre of margin), so the ride stays inside for a while.
DEEP_CORE_SHARE = 0.30


def inner_box(bbox: BBox, share: float = EDGE_SHARE) -> BBox:
    """The central part of the box, `share` of each dimension away from every side."""
    d_lat = (bbox.max_lat - bbox.min_lat) * share
    d_lon = (bbox.max_lon - bbox.min_lon) * share
    return BBox(
        bbox.min_lat + d_lat, bbox.max_lat - d_lat, bbox.min_lon + d_lon, bbox.max_lon - d_lon
    )


def in_edge_band(point: tuple[float, float], bbox: BBox) -> bool:
    """Inside the box but outside its core: within EDGE_SHARE of one of the sides."""
    return in_bbox(point, bbox) and not in_bbox(point, inner_box(bbox))


def random_edge_point(
    bbox: BBox, rng: random.Random, near: tuple[float, float] | None = None
) -> tuple[float, float]:
    """A point in the outer band of the box, within EDGE_SHARE of one side.

    With `near`, the side closest to that position is chosen and the point lies roughly
    opposite it (a rider reaches it by the shortest way); otherwise a random side and a
    random position along it.
    """
    core = inner_box(bbox)
    if near is None:
        side = rng.randrange(4)
    else:
        lat, lon = near
        distances = [
            (lat - bbox.min_lat) * 111.2,  # south, km
            (bbox.max_lat - lat) * 111.2,  # north
            (lon - bbox.min_lon) * 81.5,  # west (km per degree of longitude at ~42.9° N)
            (bbox.max_lon - lon) * 81.5,  # east
        ]
        side = distances.index(min(distances))

    def along(value: float | None, low: float, high: float, jitter: float) -> float:
        if value is None:
            return rng.uniform(low, high)
        return min(high, max(low, value + rng.uniform(-jitter, jitter)))

    near_lat = near[0] if near else None
    near_lon = near[1] if near else None
    # the outer half of the band: far enough beyond the service zone to stay outside a while
    south = (bbox.min_lat, (bbox.min_lat + core.min_lat) / 2)
    north = ((core.max_lat + bbox.max_lat) / 2, bbox.max_lat)
    west = (bbox.min_lon, (bbox.min_lon + core.min_lon) / 2)
    east = ((core.max_lon + bbox.max_lon) / 2, bbox.max_lon)
    if side == 0:
        return rng.uniform(*south), along(near_lon, bbox.min_lon, bbox.max_lon, 0.004)
    if side == 1:
        return rng.uniform(*north), along(near_lon, bbox.min_lon, bbox.max_lon, 0.004)
    if side == 2:
        return along(near_lat, bbox.min_lat, bbox.max_lat, 0.003), rng.uniform(*west)
    return along(near_lat, bbox.min_lat, bbox.max_lat, 0.003), rng.uniform(*east)
