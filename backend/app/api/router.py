from fastapi import APIRouter

from app.api import health, scooters, ws

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(scooters.router, tags=["scooters"])
api_router.include_router(ws.router, tags=["realtime"])
