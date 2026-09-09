from fastapi import APIRouter

from app.schemas.health import HealthResponse

router = APIRouter()


@router.get("/health", summary="Liveness probe")
async def get_health() -> HealthResponse:
    """Report that the API process is up. Does not touch the database."""
    return HealthResponse()
