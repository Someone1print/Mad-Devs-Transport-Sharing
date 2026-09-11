from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


async def test_create_user_returns_id_and_name(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    response = await client.post("/api/users", json={"name": "  Айбек  "})

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Айбек"
    assert isinstance(body["id"], int)
    assert "created_at" in body


async def test_create_user_rejects_blank_name(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    response = await client.post("/api/users", json={"name": "   "})

    assert response.status_code == 422


async def test_me_returns_the_user_named_in_the_header(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    created = (await client.post("/api/users", json={"name": "Dana"})).json()

    response = await client.get("/api/users/me", headers={"X-User-Id": str(created["id"])})

    assert response.status_code == 200
    assert response.json() == created


async def test_me_without_header_is_unauthorized(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    response = await client.get("/api/users/me")

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "user_required"


async def test_me_with_unknown_or_malformed_id_is_unauthorized(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    unknown = await client.get("/api/users/me", headers={"X-User-Id": "999999"})
    malformed = await client.get("/api/users/me", headers={"X-User-Id": "abc"})

    assert unknown.status_code == 401
    assert malformed.status_code == 401
