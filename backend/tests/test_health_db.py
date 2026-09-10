from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


async def test_health_db_reports_ok_when_database_answers(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    response = await client.get("/api/health/db")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


async def test_health_db_reports_unavailable_when_database_fails(client: AsyncClient) -> None:
    from collections.abc import AsyncIterator

    from sqlalchemy.exc import OperationalError

    from app.db.session import get_db
    from app.main import app

    class BrokenSession:
        async def execute(self, *_args: object, **_kwargs: object) -> None:
            raise OperationalError("SELECT 1", {}, Exception("connection refused"))

    async def broken_db() -> AsyncIterator[BrokenSession]:
        yield BrokenSession()

    app.dependency_overrides[get_db] = broken_db
    try:
        response = await client.get("/api/health/db")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 503
    assert response.json() == {"status": "error", "database": "unavailable"}
