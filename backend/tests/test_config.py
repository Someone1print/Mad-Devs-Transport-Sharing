import pytest

from app.core.config import Settings


def test_database_url_is_built_from_postgres_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POSTGRES_HOST", "db")
    monkeypatch.setenv("POSTGRES_PORT", "5433")
    monkeypatch.setenv("POSTGRES_USER", "rider")
    monkeypatch.setenv("POSTGRES_PASSWORD", "p@ss:word")
    monkeypatch.setenv("POSTGRES_DB", "scooters")

    settings = Settings(_env_file=None)

    assert settings.database_url == "postgresql+asyncpg://rider:p%40ss%3Aword@db:5433/scooters"


def test_auto_finish_threshold_must_not_exceed_the_low_battery_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # a scooter that ran flat mid-ride is unavailable; a higher auto-finish threshold would let
    # telemetry flip it back to available and the next rider start a ride that ends at once
    monkeypatch.setenv("LOW_BATTERY_THRESHOLD", "15")
    monkeypatch.setenv("RIDE_AUTO_FINISH_BATTERY", "20")

    with pytest.raises(ValueError, match="must not exceed"):
        Settings(_env_file=None)

    monkeypatch.setenv("RIDE_AUTO_FINISH_BATTERY", "15")
    assert Settings(_env_file=None).ride_auto_finish_battery == 15
