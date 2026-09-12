from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ServiceZone
from app.seed import seed_zones
from app.zones import BISHKEK_CENTER_ZONE


async def test_seed_zones_inserts_the_centre_zone_once(db_session: AsyncSession) -> None:
    first = await seed_zones(db_session)
    second = await seed_zones(db_session)

    assert first == 1 and second == 0
    assert await db_session.scalar(select(func.count()).select_from(ServiceZone)) == 1
    zone = await db_session.scalar(select(ServiceZone))
    assert zone is not None and zone.name == BISHKEK_CENTER_ZONE.name
    assert zone.as_points() == list(BISHKEK_CENTER_ZONE.points)


async def test_zones_endpoint_lists_polygons(client: AsyncClient, db_session: AsyncSession) -> None:
    await seed_zones(db_session)

    response = await client.get("/api/zones")

    assert response.status_code == 200
    zones = response.json()
    assert len(zones) == 1
    assert zones[0]["name"] == BISHKEK_CENTER_ZONE.name
    assert len(zones[0]["points"]) == len(BISHKEK_CENTER_ZONE.points)
    assert zones[0]["points"][0] == {
        "lat": BISHKEK_CENTER_ZONE.points[0].lat,
        "lon": BISHKEK_CENTER_ZONE.points[0].lon,
    }
    assert isinstance(zones[0]["id"], int)
