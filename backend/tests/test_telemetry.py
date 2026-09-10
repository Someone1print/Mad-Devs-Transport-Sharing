from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Scooter, ScooterStatus


async def _add_scooter(
    session: AsyncSession,
    code: str = "KG-100",
    battery: int = 80,
    status: ScooterStatus = ScooterStatus.AVAILABLE,
) -> Scooter:
    scooter = Scooter(code=code, lat=42.8700, lon=74.5900, battery=battery, status=status)
    session.add(scooter)
    await session.commit()
    return scooter


async def test_telemetry_updates_position_and_battery(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    scooter = await _add_scooter(db_session)
    before = scooter.updated_at

    response = await client.post(
        "/api/telemetry", json={"code": "KG-100", "lat": 42.8800, "lon": 74.6000, "battery": 75}
    )

    assert response.status_code == 200
    body = response.json()
    assert (body["code"], body["lat"], body["lon"], body["battery"]) == ("KG-100", 42.88, 74.6, 75)
    assert body["status"] == "available"

    db_session.expire_all()
    stored = await db_session.scalar(select(Scooter).where(Scooter.code == "KG-100"))
    assert stored is not None
    assert (stored.lat, stored.lon, stored.battery) == (42.88, 74.6, 75)
    assert stored.updated_at > before


async def test_telemetry_below_threshold_marks_scooter_unavailable(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _add_scooter(db_session, battery=40)

    response = await client.post(
        "/api/telemetry", json={"code": "KG-100", "lat": 42.87, "lon": 74.59, "battery": 14}
    )

    assert response.status_code == 200
    assert response.json()["status"] == "unavailable"
    db_session.expire_all()
    stored = await db_session.scalar(select(Scooter).where(Scooter.code == "KG-100"))
    assert stored is not None
    assert stored.status is ScooterStatus.UNAVAILABLE


async def test_telemetry_with_healthy_battery_recovers_unavailable_scooter(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _add_scooter(db_session, battery=5, status=ScooterStatus.UNAVAILABLE)

    response = await client.post(
        "/api/telemetry", json={"code": "KG-100", "lat": 42.87, "lon": 74.59, "battery": 95}
    )

    assert response.status_code == 200
    assert response.json()["status"] == "available"


async def test_telemetry_for_unknown_scooter_returns_404(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    response = await client.post(
        "/api/telemetry", json={"code": "KG-999", "lat": 42.87, "lon": 74.59, "battery": 50}
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Scooter KG-999 not found"}


async def test_telemetry_rejects_values_out_of_range(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _add_scooter(db_session)

    too_much_battery = await client.post(
        "/api/telemetry", json={"code": "KG-100", "lat": 42.87, "lon": 74.59, "battery": 101}
    )
    bad_latitude = await client.post(
        "/api/telemetry", json={"code": "KG-100", "lat": 91.0, "lon": 74.59, "battery": 50}
    )

    assert too_much_battery.status_code == 422
    assert bad_latitude.status_code == 422
