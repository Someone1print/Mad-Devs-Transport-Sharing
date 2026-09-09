from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Scooter, ScooterStatus
from app.seed import SEED_SCOOTERS, seed_scooters

THRESHOLD = 15


async def test_seed_fills_an_empty_table_and_applies_battery_rule(db_session: AsyncSession) -> None:
    inserted = await seed_scooters(db_session, threshold=THRESHOLD)

    assert inserted == len(SEED_SCOOTERS) >= 15
    scooters = (await db_session.scalars(select(Scooter))).all()
    assert len(scooters) == len(SEED_SCOOTERS)
    low = [s for s in scooters if s.battery < THRESHOLD]
    assert low, "the demo fleet should include low-battery scooters"
    assert all(s.status is ScooterStatus.UNAVAILABLE for s in low)
    assert all(s.status is ScooterStatus.AVAILABLE for s in scooters if s.battery >= THRESHOLD)


async def test_seed_is_idempotent(db_session: AsyncSession) -> None:
    await seed_scooters(db_session, threshold=THRESHOLD)

    inserted_again = await seed_scooters(db_session, threshold=THRESHOLD)

    assert inserted_again == 0
    assert await db_session.scalar(select(func.count()).select_from(Scooter)) == len(SEED_SCOOTERS)
