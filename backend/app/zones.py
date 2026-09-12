"""Built-in service zones, seeded into the database on first start."""

from dataclasses import dataclass

from app.geo import Point


@dataclass(frozen=True)
class ZoneDefinition:
    name: str
    points: tuple[Point, ...]


# A decagon around the centre of Bishkek: roughly Zhibek Zholu in the north, the railway in the
# south, Manas avenue in the west and Ibraimov street in the east. The simulator's riding area
# (SIM_RIDE_BBOX) is deliberately wider, so rides can end up outside this zone.
BISHKEK_CENTER_ZONE = ZoneDefinition(
    name="Центр Бишкека",
    points=(
        Point(42.8880, 74.5900),
        Point(42.8885, 74.6060),
        Point(42.8860, 74.6200),
        Point(42.8790, 74.6225),
        Point(42.8700, 74.6215),
        Point(42.8630, 74.6120),
        Point(42.8615, 74.5950),
        Point(42.8640, 74.5800),
        Point(42.8730, 74.5775),
        Point(42.8830, 74.5790),
    ),
)
