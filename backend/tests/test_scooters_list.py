from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Scooter, ScooterStatus


async def test_list_scooters_returns_every_scooter_ordered_by_code(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    db_session.add_all(
        [
            Scooter(code="KG-B", lat=42.87, lon=74.59, battery=50),
            Scooter(code="KG-A", lat=42.88, lon=74.60, battery=9, status=ScooterStatus.UNAVAILABLE),
        ]
    )
    await db_session.commit()

    response = await client.get("/api/scooters")

    assert response.status_code == 200
    body = response.json()
    assert [s["code"] for s in body] == ["KG-A", "KG-B"]
    assert body[0]["status"] == "unavailable"
    assert body[0]["battery"] == 9
    assert set(body[1]) == {"code", "lat", "lon", "battery", "status", "updated_at"}


async def test_list_scooters_is_empty_without_data(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    response = await client.get("/api/scooters")

    assert response.status_code == 200
    assert response.json() == []
