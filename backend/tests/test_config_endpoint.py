from httpx import AsyncClient

from app.core.config import settings


async def test_public_config_exposes_booking_timings(client: AsyncClient) -> None:
    response = await client.get("/api/config")

    assert response.status_code == 200
    assert response.json() == {
        "booking_ttl_seconds": settings.booking_ttl_seconds,
        "booking_warn_before_seconds": settings.booking_warn_before_seconds,
        "low_battery_threshold": settings.low_battery_threshold,
    }
