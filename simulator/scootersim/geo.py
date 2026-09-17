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

Point = tuple[float, float]
Polygon = list[Point]


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


def in_bbox(point: tuple[float, float], bbox: BBox) -> bool:
    lat, lon = point
    return bbox.min_lat <= lat <= bbox.max_lat and bbox.min_lon <= lon <= bbox.max_lon


def inner_box(bbox: BBox, share: float) -> BBox:
    """The central part of the box, `share` of each dimension away from every side."""
    d_lat = (bbox.max_lat - bbox.min_lat) * share
    d_lon = (bbox.max_lon - bbox.min_lon) * share
    return BBox(
        bbox.min_lat + d_lat, bbox.max_lat - d_lat, bbox.min_lon + d_lon, bbox.max_lon - d_lon
    )


def bbox_polygon(bbox: BBox) -> Polygon:
    """The box as a ring of four corners, so box and zone share one code path."""
    return [
        (bbox.min_lat, bbox.min_lon),
        (bbox.min_lat, bbox.max_lon),
        (bbox.max_lat, bbox.max_lon),
        (bbox.max_lat, bbox.min_lon),
    ]


def point_in_polygon(point: Point, polygon: Polygon) -> bool:
    """Even-odd rule (a ray cast along the longitude axis), the same test the backend applies.

    Good enough to keep a simulated rider inside the service zone; a point exactly on the
    border counts as outside, so the rider turns around before touching it.
    """
    if len(polygon) < 3:
        return False
    lat, lon = point
    inside = False
    for i, (a_lat, a_lon) in enumerate(polygon):
        b_lat, b_lon = polygon[(i + 1) % len(polygon)]
        if (a_lon > lon) != (b_lon > lon):
            edge_lat = a_lat + (lon - a_lon) * (b_lat - a_lat) / (b_lon - a_lon)
            if lat < edge_lat:
                inside = not inside
    return inside


def polygon_bbox(polygon: Polygon) -> BBox:
    lats = [lat for lat, _ in polygon]
    lons = [lon for _, lon in polygon]
    return BBox(min(lats), max(lats), min(lons), max(lons))


def random_point_in_polygon(polygon: Polygon, rng: random.Random, tries: int = 1000) -> Point:
    """A uniformly random point inside the polygon (rejection sampling over its bounding box).

    A sane zone needs a handful of tries; a degenerate one falls back to the centroid of its
    vertices so the caller always gets a point.
    """
    box = polygon_bbox(polygon)
    for _ in range(tries):
        point = random_point(box, rng)
        if point_in_polygon(point, polygon):
            return point
    return sum(lat for lat, _ in polygon) / len(polygon), sum(lon for _, lon in polygon) / len(
        polygon
    )
