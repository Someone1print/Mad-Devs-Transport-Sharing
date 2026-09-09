import asyncio
import logging
from typing import Any, Protocol

from app.schemas.scooter import ScooterOut

logger = logging.getLogger(__name__)


class Client(Protocol):
    async def send_json(self, data: Any) -> None: ...


class ScooterHub:
    """Delivers every scooter update to all connected WebSocket clients.

    State lives in this process only, which is fine for a single uvicorn worker. Running
    several workers would require a shared broker (e.g. Redis pub/sub) behind the same API.
    """

    def __init__(self) -> None:
        self._clients: set[Client] = set()

    @property
    def client_count(self) -> int:
        return len(self._clients)

    def register(self, client: Client) -> None:
        self._clients.add(client)

    def unregister(self, client: Client) -> None:
        self._clients.discard(client)

    async def broadcast(self, message: dict[str, Any]) -> None:
        """Send `message` to every client; clients that fail to receive are dropped."""
        clients = list(self._clients)
        results = await asyncio.gather(
            *(client.send_json(message) for client in clients), return_exceptions=True
        )
        for client, result in zip(clients, results, strict=True):
            if isinstance(result, BaseException):
                logger.info("Dropping websocket client after send failure: %r", result)
                self._clients.discard(client)


def scooter_updated_event(scooter: ScooterOut) -> dict[str, Any]:
    return {"type": "scooter.updated", "scooter": scooter.model_dump(mode="json")}


hub = ScooterHub()
