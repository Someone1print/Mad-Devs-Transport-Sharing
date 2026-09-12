"""Ride billing: pure arithmetic on Decimal money, no database, no floats.

The rule (see DEVLOG, day 4): every segment is billed per second in proportion to its
per-minute rate, rounded to the kopeck half-up ON ITS OWN. A ride's receipt is *defined* as the
sum of its segment costs, so the breakdown always adds up to the total.
"""

import enum
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal

KOPECK = Decimal("0.01")
SECONDS_PER_MINUTE = Decimal(60)
ZERO = Decimal("0.00")


class SegmentKind(enum.StrEnum):
    RIDE = "ride"
    PAUSE = "pause"


@dataclass(frozen=True)
class Segment:
    kind: SegmentKind
    seconds: int


@dataclass(frozen=True)
class Receipt:
    ride_seconds: int
    pause_seconds: int
    ride_cost: Decimal
    pause_cost: Decimal
    total_cost: Decimal


def segment_cost(rate_per_minute: Decimal, seconds: int) -> Decimal:
    """Price of `seconds` at `rate_per_minute`, rounded to the kopeck half-up."""
    if not isinstance(rate_per_minute, Decimal):
        raise TypeError("rate_per_minute must be a Decimal, never a float")
    if seconds < 0:
        raise ValueError("seconds must not be negative")
    exact = rate_per_minute * seconds / SECONDS_PER_MINUTE
    return exact.quantize(KOPECK, rounding=ROUND_HALF_UP)


def duration_seconds(started_at: datetime, ended_at: datetime) -> int:
    """Whole seconds between two instants; the fractional second is not billed."""
    if ended_at < started_at:
        raise ValueError("a segment cannot end before it starts")
    return int((ended_at - started_at).total_seconds())


def bill(segments: Iterable[Segment], ride_rate: Decimal, pause_rate: Decimal) -> Receipt:
    """Sum the segments kind by kind; the total is the sum of the lines by construction."""
    ride_seconds = pause_seconds = 0
    ride_cost = pause_cost = ZERO
    for segment in segments:
        if segment.kind is SegmentKind.RIDE:
            ride_seconds += segment.seconds
            ride_cost += segment_cost(ride_rate, segment.seconds)
        else:
            pause_seconds += segment.seconds
            pause_cost += segment_cost(pause_rate, segment.seconds)
    return Receipt(
        ride_seconds=ride_seconds,
        pause_seconds=pause_seconds,
        ride_cost=ride_cost,
        pause_cost=pause_cost,
        total_cost=ride_cost + pause_cost,
    )
