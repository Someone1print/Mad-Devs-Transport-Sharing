import asyncio
import os
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy import make_url, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.db.session import get_db
from app.main import app

BACKEND_DIR = Path(__file__).resolve().parent.parent

# The application-level sweeper loop would run against the dev database from inside the
# TestClient lifespan; tests call the sweeper explicitly on the test database instead.
settings.booking_sweeper_enabled = False


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Every test that touches the test database gets the `db` marker automatically."""
    for item in items:
        fixtures = getattr(item, "fixturenames", ())
        if "db_session" in fixtures or "committed_db" in fixtures:
            item.add_marker(pytest.mark.db)


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    """HTTP client talking to the FastAPI app in-process (no server, no network)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as async_client:
        yield async_client


def _database_url(database: str) -> str:
    url = make_url(settings.database_url).set(database=database)
    return url.render_as_string(hide_password=False)


async def _run_admin_sql(statements: list[str]) -> None:
    """Execute statements on the maintenance database with autocommit (CREATE/DROP DATABASE)."""
    engine = create_async_engine(_database_url("postgres"), isolation_level="AUTOCOMMIT")
    try:
        async with engine.connect() as connection:
            for statement in statements:
                await connection.execute(text(statement))
    finally:
        await engine.dispose()


@pytest.fixture(scope="session")
def test_database_url() -> Iterator[str]:
    """Create `<POSTGRES_DB>_test`, migrate it to head, drop it after the session.

    A real PostgreSQL is required (locally: `docker compose up -d db`). If it is unreachable
    the db tests fail loudly instead of being skipped, so CI cannot silently miss them.
    """
    name = os.environ.get("POSTGRES_TEST_DB") or f"{settings.postgres_db}_test"
    url = _database_url(name)
    recreate = [f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)', f'CREATE DATABASE "{name}"']
    try:
        asyncio.run(_run_admin_sql(recreate))
    except Exception as exc:  # any connection problem should surface the same way
        pytest.fail(
            f"PostgreSQL is unreachable at {_database_url('postgres')}: {exc!r}. "
            "Locally run: docker compose up -d db"
        )

    alembic_config = Config(str(BACKEND_DIR / "alembic.ini"))
    alembic_config.attributes["sqlalchemy_url"] = url
    command.upgrade(alembic_config, "head")

    yield url

    asyncio.run(_run_admin_sql([f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)']))


@pytest.fixture
async def db_session(test_database_url: str) -> AsyncIterator[AsyncSession]:
    """One outer transaction per test, rolled back at teardown; the app sees this session."""
    engine = create_async_engine(test_database_url)
    async with engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(
            bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False
        )

        async def override_get_db() -> AsyncIterator[AsyncSession]:
            yield session

        app.dependency_overrides[get_db] = override_get_db
        try:
            yield session
        finally:
            app.dependency_overrides.pop(get_db, None)
            await session.close()
            await transaction.rollback()
    await engine.dispose()


@pytest.fixture
async def committed_db(test_database_url: str) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """Real sessions with real commits, one per request: needed to test row locks and races.

    Unlike `db_session` nothing is rolled back, so the tables are truncated afterwards.
    """
    engine = create_async_engine(test_database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_get_db() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield factory
    finally:
        app.dependency_overrides.pop(get_db, None)
        async with engine.begin() as connection:
            tables = "ride_segments, rides, bookings, users, scooters, service_zones"
            await connection.execute(text(f"TRUNCATE TABLE {tables} RESTART IDENTITY CASCADE"))
        await engine.dispose()
