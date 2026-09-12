"""Single source of "now" for request handlers, so tests can control time without sleeping."""

from datetime import UTC, datetime


def now() -> datetime:
    return datetime.now(UTC)
