import pytest

from app.geo import Point, point_in_polygon
from app.zones import BISHKEK_CENTER_ZONE

SQUARE = [Point(0.0, 0.0), Point(0.0, 10.0), Point(10.0, 10.0), Point(10.0, 0.0)]

# a "C" shape: concave polygon with a notch on the right side
C_SHAPE = [
    Point(0.0, 0.0),
    Point(0.0, 10.0),
    Point(10.0, 10.0),
    Point(10.0, 7.0),
    Point(4.0, 7.0),
    Point(4.0, 3.0),
    Point(10.0, 3.0),
    Point(10.0, 0.0),
]


@pytest.mark.parametrize(
    ("point", "inside"),
    [
        (Point(5.0, 5.0), True),
        (Point(0.1, 0.1), True),
        (Point(-0.1, 5.0), False),
        (Point(10.1, 5.0), False),
        (Point(5.0, 10.1), False),
        (Point(50.0, 50.0), False),
    ],
)
def test_square_inside_and_outside(point: Point, inside: bool) -> None:
    assert point_in_polygon(point, SQUARE) is inside


@pytest.mark.parametrize(
    "point",
    [
        Point(0.0, 5.0),  # on the left edge
        Point(5.0, 0.0),  # on the bottom edge
        Point(10.0, 10.0),  # on a vertex
        Point(0.0, 0.0),  # on the first vertex
        Point(10.0, 2.5),  # on the right edge
    ],
)
def test_boundary_points_count_as_inside(point: Point) -> None:
    assert point_in_polygon(point, SQUARE) is True


def test_polygon_may_be_given_closed_or_open() -> None:
    closed = [*SQUARE, SQUARE[0]]

    assert point_in_polygon(Point(5.0, 5.0), closed) is True
    assert point_in_polygon(Point(11.0, 5.0), closed) is False


@pytest.mark.parametrize(
    ("point", "inside"),
    [
        (Point(2.0, 5.0), True),  # in the spine of the C
        (Point(7.0, 5.0), False),  # in the notch: outside
        (Point(7.0, 8.5), True),  # upper arm
        (Point(7.0, 1.5), True),  # lower arm
        (Point(4.0, 5.0), True),  # on the notch's inner edge
        (Point(12.0, 5.0), False),
    ],
)
def test_concave_polygon(point: Point, inside: bool) -> None:
    assert point_in_polygon(point, C_SHAPE) is inside


def test_ray_through_a_vertex_is_not_double_counted() -> None:
    # a diamond; the horizontal ray from the centre-left point passes exactly through a vertex
    diamond = [Point(5.0, 0.0), Point(10.0, 5.0), Point(5.0, 10.0), Point(0.0, 5.0)]

    assert point_in_polygon(Point(2.0, 5.0), diamond) is True
    assert point_in_polygon(Point(-2.0, 5.0), diamond) is False
    assert point_in_polygon(Point(12.0, 5.0), diamond) is False


def test_degenerate_polygons_contain_nothing() -> None:
    assert point_in_polygon(Point(0.0, 0.0), []) is False
    assert point_in_polygon(Point(0.0, 0.0), [Point(0.0, 0.0), Point(1.0, 1.0)]) is False


@pytest.mark.parametrize(
    ("name", "point", "inside"),
    [
        ("Ala-Too Square", Point(42.8756, 74.6036), True),
        ("Chuy / Manas", Point(42.8757, 74.5878), True),
        ("Osh Bazaar", Point(42.8747, 74.5731), False),
        ("Manas airport direction (north)", Point(42.9300, 74.6000), False),
        ("south of the railway", Point(42.8500, 74.6000), False),
    ],
)
def test_real_service_zone_around_bishkek_centre(name: str, point: Point, inside: bool) -> None:
    assert point_in_polygon(point, BISHKEK_CENTER_ZONE.points) is inside, name
