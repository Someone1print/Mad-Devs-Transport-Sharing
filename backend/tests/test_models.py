import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Scooter, ScooterStatus


async def test_scooter_round_trip_sets_defaults(db_session: AsyncSession) -> None:
    db_session.add(Scooter(code="KG-TEST", lat=42.87, lon=74.59, battery=80))
    await db_session.commit()

    stored = await db_session.scalar(select(Scooter).where(Scooter.code == "KG-TEST"))

    assert stored is not None
    assert stored.id is not None
    assert stored.status is ScooterStatus.AVAILABLE
    assert stored.updated_at.tzinfo is not None
    assert (stored.lat, stored.lon, stored.battery) == (42.87, 74.59, 80)


async def test_scooter_battery_outside_0_100_is_rejected(db_session: AsyncSession) -> None:
    db_session.add(Scooter(code="KG-BAD", lat=42.87, lon=74.59, battery=101))

    with pytest.raises(IntegrityError):
        await db_session.commit()


async def test_scooter_code_is_unique(db_session: AsyncSession) -> None:
    db_session.add(Scooter(code="KG-DUP", lat=42.87, lon=74.59, battery=50))
    await db_session.commit()
    db_session.add(Scooter(code="KG-DUP", lat=42.88, lon=74.60, battery=60))

    with pytest.raises(IntegrityError):
        await db_session.commit()
