from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.realtime.hub import hub

router = APIRouter()


@router.websocket("/ws")
async def scooter_updates(websocket: WebSocket) -> None:
    """Push channel: the server sends `scooter.updated` events; client messages are ignored."""
    await websocket.accept()
    hub.register(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        hub.unregister(websocket)
