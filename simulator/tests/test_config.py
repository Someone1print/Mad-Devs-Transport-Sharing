import pytest

from scootersim.config import Config


def test_config_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("BACKEND_URL", "SIM_ACTIVE_SCOOTERS", "SIM_INTERVAL_SECONDS"):
        monkeypatch.delenv(name, raising=False)

    config = Config.from_env()

    assert config.backend_url == "http://localhost:8000"
    assert config.active_scooters == 6
    assert config.interval_seconds == 1.5
    assert config.refresh_every_ticks == 2


def test_config_reads_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BACKEND_URL", "http://backend:8000/")
    monkeypatch.setenv("SIM_ACTIVE_SCOOTERS", "3")
    monkeypatch.setenv("SIM_INTERVAL_SECONDS", "2")
    monkeypatch.setenv("SIM_USER_RIDE_DRAIN_PER_MINUTE", "30")

    config = Config.from_env()

    assert config.backend_url == "http://backend:8000"  # trailing slash stripped
    assert config.active_scooters == 3
    assert config.interval_seconds == 2.0
    assert config.user_ride_drain_per_minute == 30.0
