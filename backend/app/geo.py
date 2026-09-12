"""Planar point-in-polygon for city-scale service zones (no PostGIS, see DEVLOG day 4).

Latitude and longitude are treated as plain x/y coordinates. At the size of a service zone
(a few kilometres) neither the curvature of the Earth nor the different metric scale of the
two axes can change on which side of an edge a point lies, so the approximation is exact for
our purpose. Boundary points count as inside, in the rider's favour.
"""

from collections.abc import Sequence
from typing import NamedTuple


class Point(NamedTuple):
    lat: float
    lon: float


# Boundary rule: a point whose cross product with an edge is within this tolerance (degrees²;
# for the ~1.5 km edges of the service zone that is a band of roughly 10 micrometres) lies ON
# the boundary and counts as inside. Beyond it the even-odd rule decides. The TypeScript mirror
# (frontend/src/ride/geo.ts) uses the same constant and the same operation order, so both give
# bit-identical answers; shared/billing-cases.json pins every vertex and edge midpoint.
BOUNDARY_EPS = 1e-12


def _on_segment(p: Point, a: Point, b: Point) -> bool:
    """True if `p` lies on the closed segment a-b (collinear and within the bounding box)."""
    cross = (b.lat - a.lat) * (p.lon - a.lon) - (b.lon - a.lon) * (p.lat - a.lat)
    if abs(cross) > BOUNDARY_EPS:
        return False
    return min(a.lat, b.lat) <= p.lat <= max(a.lat, b.lat) and min(a.lon, b.lon) <= p.lon <= max(
        a.lon, b.lon
    )


def point_in_polygon(point: Point, polygon: Sequence[Point]) -> bool:
    """Even-odd ray casting; the polygon may be given open or closed (last point == first)."""
    vertices = list(polygon)
    if len(vertices) >= 2 and vertices[0] == vertices[-1]:
        vertices.pop()
    if len(vertices) < 3:
        return False

    inside = False
    for index, a in enumerate(vertices):
        b = vertices[(index + 1) % len(vertices)]
        if _on_segment(point, a, b):
            return True
        # cast the ray along +lat; the half-open test on lon makes a vertex hit count once
        if (a.lon > point.lon) != (b.lon > point.lon):
            lat_at_ray = a.lat + (point.lon - a.lon) * (b.lat - a.lat) / (b.lon - a.lon)
            if point.lat < lat_at_ray:
                inside = not inside
    return inside
