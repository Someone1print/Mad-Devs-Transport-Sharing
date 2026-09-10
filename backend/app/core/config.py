from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL


class Settings(BaseSettings):
    """Runtime configuration, read from environment variables (and `.env` files for local runs).

    Inside docker-compose the variables come from the `environment` section of the backend
    service; when running the backend directly, `../.env` (repo root) and `.env` (backend dir)
    are picked up, the latter taking precedence.
    """

    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    debug: bool = False

    # Scooters whose battery is strictly below this percentage become unavailable.
    low_battery_threshold: int = Field(default=15, ge=0, le=100)

    # Bookings: how long a hold lasts, how early the rider is warned, how often the
    # background sweeper checks expires_at. Tests set these to seconds instead of minutes.
    booking_ttl_seconds: int = Field(default=900, gt=0)
    booking_warn_before_seconds: int = Field(default=180, ge=0)
    booking_sweep_interval_seconds: float = Field(default=2.0, gt=0)

    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "scooter"
    postgres_password: str = "scooter"
    postgres_db: str = "scooter"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def database_url(self) -> str:
        """SQLAlchemy URL for the asyncpg driver, with credentials properly escaped."""
        url = URL.create(
            drivername="postgresql+asyncpg",
            username=self.postgres_user,
            password=self.postgres_password,
            host=self.postgres_host,
            port=self.postgres_port,
            database=self.postgres_db,
        )
        return url.render_as_string(hide_password=False)


settings = Settings()
