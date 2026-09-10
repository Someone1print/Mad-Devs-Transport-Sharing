import pytest

from app.core.config import Settings
from app.models import ScooterStatus
from app.services.scooters import status_after_telemetry

THRESHOLD = 15


@pytest.mark.parametrize(
    "current",
    [
        ScooterStatus.AVAILABLE,
        ScooterStatus.RESERVED,
        ScooterStatus.RIDING,
        ScooterStatus.UNAVAILABLE,
    ],
)
def test_battery_below_threshold_makes_scooter_unavailable(current: ScooterStatus) -> None:
    assert (
        status_after_telemetry(current, battery=14, threshold=THRESHOLD)
        is ScooterStatus.UNAVAILABLE
    )


def test_battery_exactly_at_threshold_is_not_low() -> None:
    assert status_after_telemetry(ScooterStatus.AVAILABLE, 15, THRESHOLD) is ScooterStatus.AVAILABLE


def test_unavailable_scooter_recovers_when_battery_is_back() -> None:
    assert (
        status_after_telemetry(ScooterStatus.UNAVAILABLE, 90, THRESHOLD) is ScooterStatus.AVAILABLE
    )


@pytest.mark.parametrize(
    "current", [ScooterStatus.AVAILABLE, ScooterStatus.RESERVED, ScooterStatus.RIDING]
)
def test_healthy_battery_keeps_business_status(current: ScooterStatus) -> None:
    assert status_after_telemetry(current, battery=50, threshold=THRESHOLD) is current


def test_threshold_defaults_to_15_and_is_configurable(monkeypatch: pytest.MonkeyPatch) -> None:
    assert Settings(_env_file=None).low_battery_threshold == 15

    monkeypatch.setenv("LOW_BATTERY_THRESHOLD", "20")
    assert Settings(_env_file=None).low_battery_threshold == 20
