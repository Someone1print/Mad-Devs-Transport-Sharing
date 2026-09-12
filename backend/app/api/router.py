from fastapi import APIRouter

from app.api import bookings, config, health, scooters, users, ws, zones

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(config.router, tags=["config"])
api_router.include_router(scooters.router, tags=["scooters"])
api_router.include_router(ws.router, tags=["realtime"])
api_router.include_router(users.router, tags=["users"])
api_router.include_router(bookings.router, tags=["bookings"])
api_router.include_router(zones.router, tags=["zones"])
