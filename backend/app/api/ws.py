import json
import logging
from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from app.api.deps import SESSION_COOKIE
from app.core import clock
from app.db.session import async_session_factory
from app.realtime.hub import hub
from app.services.auth import user_from_token

router = APIRouter()
logger = logging.getLogger(__name__)

TokenAuthenticator = Callable[[str | None], Awaitable[int | None]]


async def _session_user_id(token: str | None) -> int | None:
    """The user behind a session token, looked up in a session of its own (the socket lives
    for hours; a request-scoped database session would be held open all that time)."""
    if not token:
        return None
    async with async_session_factory() as session:
        user = await user_from_token(session, token, clock.now())
        return None if user is None else user.id


def get_token_authenticator() -> TokenAuthenticator:
    """Tests override this with a token → user id mapping, so no database is needed."""
    return _session_user_id


def parse_identify(raw: str) -> str | None:
    """Return the token from an `identify` message, or None for anything else.

    A `user_id` in the message is ignored: the socket is bound to whoever the token belongs to.
    """
    try:
        message = json.loads(raw)
    except ValueError:
        return None
    if not isinstance(message, dict) or message.get("type") != "identify":
        return None
    token = message.get("token")
    return token if isinstance(token, str) and token else None


@router.websocket("/ws")
async def scooter_updates(
    websocket: WebSocket,
    authenticate: Annotated[TokenAuthenticator, Depends(get_token_authenticator)],
) -> None:
    """Push channel. Public `scooter.updated` events go to everyone; personal `booking.*`,
    `ride.*` and `email.sent` events go to sockets bound to a user — by the session cookie at
    the handshake (the browser) or by `{"type": "identify", "token": "…"}` (other clients).
    Anything else a client sends is ignored."""
    await websocket.accept()
    hub.register(websocket)
    try:
        user_id = await authenticate(websocket.cookies.get(SESSION_COOKIE))
        if user_id is not None:
            hub.identify(websocket, user_id)
        while True:
            token = parse_identify(await websocket.receive_text())
            if token is not None and (user_id := await authenticate(token)) is not None:
                hub.identify(websocket, user_id)
    except WebSocketDisconnect:
        pass
    finally:
        hub.unregister(websocket)
