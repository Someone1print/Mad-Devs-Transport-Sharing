from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.health import HealthDbResponse, HealthResponse

router = APIRouter()


@router.get("/health", summary="Liveness probe")
async def get_health() -> HealthResponse:
    """Report that the API process is up. Does not touch the database."""
    return HealthResponse()


@router.get(
    "/health/db",
    summary="Readiness probe",
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": HealthDbResponse}},
)
async def get_health_db(
    session: Annotated[AsyncSession, Depends(get_db)], response: Response
) -> HealthDbResponse:
    """Report whether the database answers a trivial query."""
    try:
        await session.execute(text("SELECT 1"))
    except (SQLAlchemyError, OSError):
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return HealthDbResponse(status="error", database="unavailable")
    return HealthDbResponse(status="ok", database="ok")
