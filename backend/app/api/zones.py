from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models import ServiceZone
from app.schemas.zone import ZoneOut

router = APIRouter()


@router.get("/zones", summary="Service zones (rides may only end inside one)")
async def get_zones(session: Annotated[AsyncSession, Depends(get_db)]) -> list[ZoneOut]:
    zones = (await session.scalars(select(ServiceZone).order_by(ServiceZone.id))).all()
    return [ZoneOut.from_zone(zone) for zone in zones]
