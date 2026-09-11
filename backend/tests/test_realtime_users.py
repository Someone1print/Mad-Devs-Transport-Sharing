from typing import Any

from fastapi.testclient import TestClient

from app.main import app
from app.realtime.hub import ScooterHub, hub


class FakeSocket:
    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []

    async def send_json(self, message: dict[str, Any]) -> None:
        self.sent.append(message)


async def test_send_to_user_reaches_only_that_users_sockets() -> None:
    local_hub = ScooterHub()
    tab_a, tab_b, other, anonymous = FakeSocket(), FakeSocket(), FakeSocket(), FakeSocket()
    for socket in (tab_a, tab_b, other, anonymous):
        local_hub.register(socket)  # type: ignore[arg-type]
    local_hub.identify(tab_a, user_id=7)  # type: ignore[arg-type]
    local_hub.identify(tab_b, user_id=7)  # type: ignore[arg-type]
    local_hub.identify(other, user_id=8)  # type: ignore[arg-type]

    delivered = await local_hub.send_to_user(7, {"type": "booking.expiring"})

    assert delivered == 2
    assert tab_a.sent == [{"type": "booking.expiring"}]
    assert tab_b.sent == [{"type": "booking.expiring"}]
    assert other.sent == []
    assert anonymous.sent == []


async def test_unregister_forgets_the_user_binding() -> None:
    local_hub = ScooterHub()
    socket = FakeSocket()
    local_hub.register(socket)  # type: ignore[arg-type]
    local_hub.identify(socket, user_id=7)  # type: ignore[arg-type]

    local_hub.unregister(socket)  # type: ignore[arg-type]

    assert await local_hub.send_to_user(7, {"type": "x"}) == 0
    assert local_hub.client_count == 0


def test_websocket_identify_message_binds_the_connection() -> None:
    with TestClient(app) as test_client, test_client.websocket_connect("/api/ws") as websocket:
        websocket.send_json({"type": "identify", "user_id": 42})
        # the server processes identify asynchronously; a public broadcast proves the loop runs
        test_client.portal.call(hub.broadcast, {"type": "ping"})
        assert websocket.receive_json() == {"type": "ping"}

        delivered = test_client.portal.call(hub.send_to_user, 42, {"type": "booking.expiring"})

        assert delivered == 1
        assert websocket.receive_json() == {"type": "booking.expiring"}


def test_websocket_ignores_garbage_messages() -> None:
    with TestClient(app) as test_client, test_client.websocket_connect("/api/ws") as websocket:
        websocket.send_text("not json")
        websocket.send_json({"type": "identify", "user_id": "not-a-number"})
        test_client.portal.call(hub.broadcast, {"type": "ping"})

        assert websocket.receive_json() == {"type": "ping"}
