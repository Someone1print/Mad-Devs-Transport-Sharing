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
