from fastapi import FastAPI

from app.api.router import api_router

API_PREFIX = "/api"


def create_app() -> FastAPI:
    application = FastAPI(
        title="Transport Sharing API",
        version="0.1.0",
        openapi_url=f"{API_PREFIX}/openapi.json",
        docs_url=f"{API_PREFIX}/docs",
        redoc_url=f"{API_PREFIX}/redoc",
    )
    application.include_router(api_router, prefix=API_PREFIX)
    return application


app = create_app()
