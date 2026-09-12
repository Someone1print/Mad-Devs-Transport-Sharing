import asyncio
import logging
from typing import Any, Protocol

from app.schemas.booking import BookingOut
from app.schemas.ride import RideOut
from app.schemas.scooter import ScooterOut

logger = logging.getLogger(__name__)


class Client(Protocol):
    async def send_json(self, data: Any) -> None: ...


class ScooterHub:
    """Delivers realtime events to WebSocket clients: public broadcasts and per-user messages.

    A client becomes addressable after `identify` (the browser sends its user id right after
    opening the socket; WebSocket handshakes cannot carry custom headers). State lives in this
    process only, which is fine for a single uvicorn worker; several workers would need a shared
    broker (e.g. Redis pub/sub) behind the same API.
    """

    def __init__(self) -> None:
        self._clients: dict[Client, int | None] = {}

    @property
    def client_count(self) -> int:
        return len(self._clients)

    def register(self, client: Client) -> None:
        self._clients[client] = None

    def identify(self, client: Client, user_id: int) -> None:
        if client in self._clients:
            self._clients[client] = user_id

    def unregister(self, client: Client) -> None:
        self._clients.pop(client, None)

    async def broadcast(self, message: dict[str, Any]) -> None:
        """Send `message` to every client; clients that fail to receive are dropped."""
        await self._deliver(list(self._clients), message)

    async def send_to_user(self, user_id: int, message: dict[str, Any]) -> int:
        """Send `message` to every socket of one user (all their tabs); returns the count."""
        targets = [client for client, owner in self._clients.items() if owner == user_id]
        await self._deliver(targets, message)
        return len(targets)

    async def _deliver(self, clients: list[Client], message: dict[str, Any]) -> None:
        results = await asyncio.gather(
            *(client.send_json(message) for client in clients), return_exceptions=True
        )
        for client, result in zip(clients, results, strict=True):
            if isinstance(result, BaseException):
                logger.info("Dropping websocket client after send failure: %r", result)
                self._clients.pop(client, None)


def scooter_updated_event(scooter: ScooterOut) -> dict[str, Any]:
    return {"type": "scooter.updated", "scooter": scooter.model_dump(mode="json")}


def booking_event(event_type: str, booking: BookingOut, **extra: Any) -> dict[str, Any]:
    """Personal event about the user's booking: booking.created / cancelled / expiring / expired."""
    return {"type": event_type, "booking": booking.model_dump(mode="json"), **extra}


def ride_event(event_type: str, ride: RideOut) -> dict[str, Any]:
    """Personal event about the user's ride: ride.started / paused / resumed / finished."""
    return {"type": event_type, "ride": ride.model_dump(mode="json")}


hub = ScooterHub()
