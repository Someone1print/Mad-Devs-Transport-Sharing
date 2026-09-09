from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db


async def test_get_db_yields_async_session_without_connecting() -> None:
    sessions = get_db()

    session = await anext(sessions)
    try:
        assert isinstance(session, AsyncSession)
    finally:
        await sessions.aclose()
