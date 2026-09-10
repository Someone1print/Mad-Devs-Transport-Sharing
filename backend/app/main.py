import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import timedelta

from fastapi import FastAPI

from app.api.router import api_router
from app.core.config import settings
from app.db.session import async_session_factory, engine
from app.realtime.hub import hub
from app.services.booking_sweeper import run_booking_sweeper

API_PREFIX = "/api"


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    """Start the booking sweeper with the process and stop it cleanly on shutdown."""
    stop = asyncio.Event()
    sweeper: asyncio.Task[None] | None = None
    if settings.booking_sweeper_enabled:
        sweeper = asyncio.create_task(
            run_booking_sweeper(
                async_session_factory,
                hub,
                interval=settings.booking_sweep_interval_seconds,
                warn_before=timedelta(seconds=settings.booking_warn_before_seconds),
                stop=stop,
            ),
            name="booking-sweeper",
        )
    application.state.booking_sweeper = sweeper
    try:
        yield
    finally:
        stop.set()
        if sweeper is not None:
            await sweeper
        await engine.dispose()


def configure_logging() -> None:
    """Make application INFO logs (e.g. the booking sweeper) visible next to uvicorn's own."""
    root = logging.getLogger()
    if not root.handlers:
        logging.basicConfig(level=logging.INFO, format="%(levelname)s [%(name)s] %(message)s")
    logging.getLogger("app").setLevel(logging.INFO)


def create_app() -> FastAPI:
    configure_logging()
    application = FastAPI(
        title="Transport Sharing API",
        version="0.1.0",
        openapi_url=f"{API_PREFIX}/openapi.json",
        docs_url=f"{API_PREFIX}/docs",
        redoc_url=f"{API_PREFIX}/redoc",
        lifespan=lifespan,
    )
    application.include_router(api_router, prefix=API_PREFIX)
    return application


app = create_app()
