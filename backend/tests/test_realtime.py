from typing import Any

from fastapi.testclient import TestClient
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.models import Scooter
from app.realtime.hub import ScooterHub, hub


class FakeSocket:
    def __init__(self, *, broken: bool = False) -> None:
        self.broken = broken
        self.sent: list[dict[str, Any]] = []

    async def send_json(self, message: dict[str, Any]) -> None:
        if self.broken:
            raise RuntimeError("connection closed")
        self.sent.append(message)


async def test_hub_broadcasts_to_every_client_and_drops_broken_ones() -> None:
    local_hub = ScooterHub()
    healthy, broken = FakeSocket(), FakeSocket(broken=True)
    local_hub.register(healthy)  # type: ignore[arg-type]
    local_hub.register(broken)  # type: ignore[arg-type]

    await local_hub.broadcast({"type": "ping"})

    assert healthy.sent == [{"type": "ping"}]
    assert local_hub.client_count == 1


async def test_telemetry_broadcasts_scooter_update(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    db_session.add(Scooter(code="KG-RT", lat=42.87, lon=74.59, battery=80))
    await db_session.commit()
    listener = FakeSocket()
    hub.register(listener)  # type: ignore[arg-type]
    try:
        response = await client.post(
            "/api/telemetry", json={"code": "KG-RT", "lat": 42.88, "lon": 74.6, "battery": 10}
        )
    finally:
        hub.unregister(listener)  # type: ignore[arg-type]

    assert response.status_code == 200
    assert len(listener.sent) == 1
    event = listener.sent[0]
    assert event["type"] == "scooter.updated"
    assert event["scooter"]["code"] == "KG-RT"
    assert event["scooter"]["status"] == "unavailable"
    assert event["scooter"] == response.json()


def test_websocket_endpoint_delivers_broadcasts() -> None:
    with TestClient(app) as test_client, test_client.websocket_connect("/api/ws") as websocket:
        assert hub.client_count == 1

        test_client.portal.call(hub.broadcast, {"type": "ping"})

        assert websocket.receive_json() == {"type": "ping"}
