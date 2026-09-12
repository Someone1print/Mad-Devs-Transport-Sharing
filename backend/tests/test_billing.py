from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.billing import (
    KOPECK,
    Receipt,
    Segment,
    SegmentKind,
    bill,
    duration_seconds,
    segment_cost,
)

RIDE = Decimal("5.00")
PAUSE = Decimal("1.50")


# --- segment_cost: the rounding rule (per second, proportional, half-up per segment) ---


@pytest.mark.parametrize(
    ("rate", "seconds", "expected"),
    [
        (RIDE, 0, "0.00"),
        (RIDE, 1, "0.08"),  # 5/60 = 0.0833…
        (RIDE, 59, "4.92"),  # 4.9166…
        (RIDE, 60, "5.00"),  # exact minute
        (RIDE, 61, "5.08"),  # 5.0833…
        (RIDE, 90, "7.50"),
        (RIDE, 119, "9.92"),
        (RIDE, 120, "10.00"),
        (PAUSE, 1, "0.03"),  # 0.025 → half-up
        (PAUSE, 30, "0.75"),
        (Decimal("7.50"), 1, "0.13"),  # 0.125 → half-up
        (Decimal("0.01"), 1, "0.00"),  # 0.000166… → rounds away entirely
        (Decimal("0.01"), 30, "0.01"),  # 0.005 → half-up
    ],
)
def test_segment_cost_vectors(rate: Decimal, seconds: int, expected: str) -> None:
    """These vectors are duplicated in frontend/src/ride/billing.test.ts — keep them in sync."""
    assert segment_cost(rate, seconds) == Decimal(expected)


def test_segment_cost_returns_decimal_with_two_places() -> None:
    cost = segment_cost(RIDE, 7)

    assert isinstance(cost, Decimal)
    assert cost.as_tuple().exponent == -2


def test_segment_cost_rejects_floats_and_negative_durations() -> None:
    with pytest.raises(TypeError):
        segment_cost(5.0, 60)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        segment_cost(RIDE, -1)


# --- duration_seconds: whole seconds, fraction dropped in the rider's favour ---


def test_duration_seconds_floors_to_whole_seconds() -> None:
    start = datetime(2026, 9, 12, 10, 0, 0, tzinfo=UTC)

    assert duration_seconds(start, start + timedelta(seconds=59, microseconds=999_999)) == 59
    assert duration_seconds(start, start + timedelta(seconds=60)) == 60
    assert duration_seconds(start, start) == 0


def test_duration_seconds_rejects_end_before_start() -> None:
    start = datetime(2026, 9, 12, 10, 0, 0, tzinfo=UTC)

    with pytest.raises(ValueError):
        duration_seconds(start, start - timedelta(seconds=1))


# --- bill: the receipt is the sum of its segments ---


def test_bill_single_ride_segment() -> None:
    receipt = bill([Segment(SegmentKind.RIDE, 600)], RIDE, PAUSE)

    assert receipt == Receipt(
        ride_seconds=600,
        pause_seconds=0,
        ride_cost=Decimal("50.00"),
        pause_cost=Decimal("0.00"),
        total_cost=Decimal("50.00"),
    )


def test_bill_pause_uses_its_own_rate() -> None:
    receipt = bill([Segment(SegmentKind.RIDE, 60), Segment(SegmentKind.PAUSE, 60)], RIDE, PAUSE)

    assert receipt.ride_cost == Decimal("5.00")
    assert receipt.pause_cost == Decimal("1.50")
    assert receipt.total_cost == Decimal("6.50")


def test_bill_multiple_pauses_at_minute_boundaries() -> None:
    segments = [
        Segment(SegmentKind.RIDE, 61),  # 5.08
        Segment(SegmentKind.PAUSE, 59),  # 1.475 → 1.48
        Segment(SegmentKind.RIDE, 1),  # 0.08
        Segment(SegmentKind.PAUSE, 1),  # 0.03
        Segment(SegmentKind.RIDE, 120),  # 10.00
        Segment(SegmentKind.PAUSE, 0),  # 0.00
        Segment(SegmentKind.RIDE, 0),  # 0.00
    ]

    receipt = bill(segments, RIDE, PAUSE)

    assert receipt.ride_seconds == 182
    assert receipt.pause_seconds == 60
    assert receipt.ride_cost == Decimal("15.16")
    assert receipt.pause_cost == Decimal("1.51")
    assert receipt.total_cost == Decimal("16.67")
    assert (
        sum(
            (
                segment_cost(RIDE if s.kind is SegmentKind.RIDE else PAUSE, s.seconds)
                for s in segments
            ),
            Decimal("0"),
        )
        == receipt.total_cost
    )


def test_bill_of_no_segments_is_zero() -> None:
    receipt = bill([], RIDE, PAUSE)

    assert receipt.total_cost == Decimal("0.00")
    assert receipt.ride_seconds == receipt.pause_seconds == 0


rates = st.decimals(min_value=Decimal("0.00"), max_value=Decimal("999.99"), places=2)
segment_lists = st.lists(
    st.builds(
        Segment,
        kind=st.sampled_from(list(SegmentKind)),
        seconds=st.integers(min_value=0, max_value=6 * 60 * 60),
    ),
    max_size=40,
)


@settings(max_examples=500)
@given(segments=segment_lists, ride_rate=rates, pause_rate=rates)
def test_no_kopeck_is_ever_lost(
    segments: list[Segment], ride_rate: Decimal, pause_rate: Decimal
) -> None:
    receipt = bill(segments, ride_rate, pause_rate)

    per_segment = [
        segment_cost(ride_rate if s.kind is SegmentKind.RIDE else pause_rate, s.seconds)
        for s in segments
    ]
    # the receipt is exactly the sum of its lines, kind by kind and in total
    assert receipt.total_cost == sum(per_segment, Decimal("0"))
    assert receipt.total_cost == receipt.ride_cost + receipt.pause_cost
    assert receipt.ride_cost == sum(
        (c for c, s in zip(per_segment, segments, strict=True) if s.kind is SegmentKind.RIDE),
        Decimal("0"),
    )
    # every amount is a Decimal with exactly two places
    for amount in (receipt.ride_cost, receipt.pause_cost, receipt.total_cost, *per_segment):
        assert isinstance(amount, Decimal)
        assert amount.as_tuple().exponent == -2
    # each line is within half a kopeck of the exact proportional price
    for cost, s in zip(per_segment, segments, strict=True):
        rate = ride_rate if s.kind is SegmentKind.RIDE else pause_rate
        assert abs(cost - rate * s.seconds / 60) <= KOPECK / 2
    assert receipt.ride_seconds == sum(s.seconds for s in segments if s.kind is SegmentKind.RIDE)
