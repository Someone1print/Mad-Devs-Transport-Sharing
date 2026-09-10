import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.realtime.hub import hub

router = APIRouter()
logger = logging.getLogger(__name__)


def parse_identify(raw: str) -> int | None:
    """Return the user id from an `identify` message, or None for anything else."""
    try:
        message = json.loads(raw)
    except ValueError:
        return None
    if not isinstance(message, dict) or message.get("type") != "identify":
        return None
    user_id = message.get("user_id")
    return user_id if isinstance(user_id, int) and not isinstance(user_id, bool) else None


@router.websocket("/ws")
async def scooter_updates(websocket: WebSocket) -> None:
    """Push channel. The server sends public `scooter.updated` events to everyone and personal
    `booking.*` events to sockets that identified themselves with
    `{"type": "identify", "user_id": <id>}`; other client messages are ignored."""
    await websocket.accept()
    hub.register(websocket)
    try:
        while True:
            user_id = parse_identify(await websocket.receive_text())
            if user_id is not None:
                hub.identify(websocket, user_id)
    except WebSocketDisconnect:
        pass
    finally:
        hub.unregister(websocket)
