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

# Where user rides may wander: deliberately wider than the backend's service zone, so a ride
# can end up outside it and the "finish only inside the zone" rule can be demonstrated.
RIDE_BBOX = BBox(min_lat=42.850, max_lat=42.900, min_lon=74.560, max_lon=74.640)


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
