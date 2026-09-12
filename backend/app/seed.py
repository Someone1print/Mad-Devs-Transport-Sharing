"""Demo data for local runs: `python -m app.seed` inserts the fleet and the service zone
into empty tables."""

import asyncio
import logging

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import async_session_factory, engine
from app.models import Scooter, ScooterStatus, ServiceZone
from app.services.scooters import status_after_telemetry
from app.zones import BISHKEK_CENTER_ZONE

logger = logging.getLogger(__name__)

# code, lat, lon, battery — points around the centre of Bishkek
SEED_SCOOTERS: list[tuple[str, float, float, int]] = [
    ("KG-001", 42.8756, 74.6036, 92),  # Ala-Too Square
    ("KG-002", 42.8747, 74.5731, 67),  # Osh Bazaar
    ("KG-003", 42.8757, 74.5878, 81),  # Chuy / Manas
    ("KG-004", 42.8760, 74.6170, 45),  # Chuy / Ibraimov
    ("KG-005", 42.8615, 74.6060, 58),  # railway station
    ("KG-006", 42.8746, 74.5900, 12),  # Bishkek Park — low battery
    ("KG-007", 42.8570, 74.5890, 73),  # Vefa Center
    ("KG-008", 42.8710, 74.6050, 88),  # Erkindik / Toktogul
    ("KG-009", 42.8790, 74.6000, 34),  # Panfilov Park
    ("KG-010", 42.8770, 74.5800, 99),  # Molodaya Gvardiya
    ("KG-011", 42.8690, 74.6130, 27),  # Abdrakhmanov / Bokonbaev
    ("KG-012", 42.8730, 74.6170, 9),  # KNU — low battery
    ("KG-013", 42.8760, 74.6120, 77),  # TsUM
    ("KG-014", 42.8800, 74.5880, 63),  # Frunze / Manas
    ("KG-015", 42.8650, 74.5780, 55),  # Jibek Jolu / Manas
    ("KG-016", 42.8830, 74.6100, 84),  # Kievskaya / Abdrakhmanov
    ("KG-017", 42.8680, 74.5950, 41),  # Toktogul / Turusbekov
    ("KG-018", 42.8880, 74.5960, 70),  # Zhibek Zholu / Erkindik
]


async def seed_scooters(session: AsyncSession, threshold: int) -> int:
    """Insert the demo fleet if the table is empty. Returns the number of inserted rows."""
    existing = await session.scalar(select(func.count()).select_from(Scooter))
    if existing:
        return 0

    session.add_all(
        Scooter(
            code=code,
            lat=lat,
            lon=lon,
            battery=battery,
            status=status_after_telemetry(ScooterStatus.AVAILABLE, battery, threshold),
        )
        for code, lat, lon, battery in SEED_SCOOTERS
    )
    await session.commit()
    return len(SEED_SCOOTERS)


async def seed_zones(session: AsyncSession) -> int:
    """Insert the built-in service zone if the table is empty. Returns the number inserted."""
    existing = await session.scalar(select(func.count()).select_from(ServiceZone))
    if existing:
        return 0
    session.add(
        ServiceZone(
            name=BISHKEK_CENTER_ZONE.name,
            points=[{"lat": p.lat, "lon": p.lon} for p in BISHKEK_CENTER_ZONE.points],
        )
    )
    await session.commit()
    return 1


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s [%(name)s] %(message)s")
    try:
        async with async_session_factory() as session:
            scooters = await seed_scooters(session, settings.low_battery_threshold)
            zones = await seed_zones(session)
    finally:
        await engine.dispose()
    logger.info(
        "Seed: %s, %s",
        f"inserted {scooters} demo scooters" if scooters else "scooters table not empty",
        f"inserted {zones} service zone" if zones else "service zones already present",
    )


if __name__ == "__main__":
    asyncio.run(main())
