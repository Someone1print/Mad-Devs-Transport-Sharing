"""The shared case set (shared/billing-cases.json) is the contract between backend and frontend.

The same file is checked by frontend/src/ride/sharedCases.test.ts. If the billing rule or the
polygon rule changes here, this test fails until the file is regenerated with
`uv run python scripts/generate_shared_cases.py` — and the frontend test then fails until the
TypeScript mirror follows.
"""

import json
from decimal import Decimal
from pathlib import Path

import pytest

from app.billing import Segment, SegmentKind, bill, segment_cost
from app.geo import Point, point_in_polygon
from app.zones import BISHKEK_CENTER_ZONE

CASES = json.loads(
    (Path(__file__).resolve().parents[2] / "shared" / "billing-cases.json").read_text(
        encoding="utf-8"
    )
)


def test_the_case_set_is_substantial() -> None:
    assert len(CASES["segment_costs"]) >= 400
    assert len(CASES["rides"]) >= 100
    assert len(CASES["zone"]["cases"]) >= 200


@pytest.mark.parametrize(
    "case", CASES["segment_costs"], ids=lambda c: f"{c['rate']}x{c['seconds']}s"
)
def test_segment_cost_matches_the_shared_case(case: dict[str, object]) -> None:
    cost = segment_cost(Decimal(str(case["rate"])), int(case["seconds"]))  # type: ignore[arg-type]

    assert str(cost) == case["cost"]


@pytest.mark.parametrize("case", CASES["rides"], ids=lambda c: f"ride{len(c['segments'])}seg")
def test_ride_receipt_matches_the_shared_case(case: dict[str, object]) -> None:
    receipt = bill(
        [Segment(SegmentKind(s["kind"]), int(s["seconds"])) for s in case["segments"]],  # type: ignore[index]
        Decimal(str(case["ride_rate"])),
        Decimal(str(case["pause_rate"])),
    )

    expected = case["expected"]
    assert receipt.ride_seconds == expected["ride_seconds"]  # type: ignore[index]
    assert receipt.pause_seconds == expected["pause_seconds"]  # type: ignore[index]
    assert str(receipt.ride_cost) == expected["ride_cost"]  # type: ignore[index]
    assert str(receipt.pause_cost) == expected["pause_cost"]  # type: ignore[index]
    assert str(receipt.total_cost) == expected["total_cost"]  # type: ignore[index]


def test_shared_zone_is_the_built_in_zone() -> None:
    assert CASES["zone"]["points"] == [
        {"lat": p.lat, "lon": p.lon} for p in BISHKEK_CENTER_ZONE.points
    ]


@pytest.mark.parametrize(
    "case", CASES["zone"]["cases"], ids=lambda c: c.get("note") or f"{c['lat']},{c['lon']}"
)
def test_point_in_zone_matches_the_shared_case(case: dict[str, object]) -> None:
    zone = [Point(p["lat"], p["lon"]) for p in CASES["zone"]["points"]]  # type: ignore[index]

    assert point_in_polygon(Point(float(case["lat"]), float(case["lon"])), zone) is case["inside"]  # type: ignore[arg-type]
