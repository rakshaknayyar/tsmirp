"""Live WebSockets.

WS /ws/dashboard  staff: every live event (incidents, status changes, geofence alerts)
WS /ws/tourist    tourists: ONLY events about their own incidents (e.g. SOS status updates)

Protocol (both):
1. Client connects.
2. Within 5 seconds the client sends: {"type": "auth", "token": "<access token>"}.
   (The token is sent as a message, not in the URL, so it never appears in server logs.)
3. Server replies {"type": "ready", "mode": "redis" | "memory"} and then pushes events.
Wrong role or bad token: the server closes the connection with code 1008 (policy violation).
"""

import asyncio
from collections.abc import Callable, Collection

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.api.deps import DbSession, user_from_access_token
from app.models.user import STAFF_ROLES, Role, User
from app.services.events import event_bus

router = APIRouter(tags=["live"])

AUTH_TIMEOUT_SECONDS = 5


async def _authenticate(websocket: WebSocket, db: Session, roles: Collection[Role]) -> User | None:
    await websocket.accept()
    try:
        first = await asyncio.wait_for(websocket.receive_json(), AUTH_TIMEOUT_SECONDS)
    except (TimeoutError, ValueError, WebSocketDisconnect):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return None
    token = first.get("token") if isinstance(first, dict) and first.get("type") == "auth" else None
    # Database calls are blocking, so run them in a worker thread.
    user = await run_in_threadpool(user_from_access_token, db, token)
    if user is None or user.role not in roles:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return None
    return user


async def _stream(websocket: WebSocket, wanted: Callable[[dict], bool]) -> None:
    """Forward every event that `wanted` accepts until the client disconnects."""
    queue = event_bus.subscribe()
    await websocket.send_json({"type": "ready", "mode": event_bus.mode})

    async def forward_events() -> None:
        while True:
            event = await queue.get()
            if wanted(event):
                await websocket.send_json(event)

    sender = asyncio.create_task(forward_events())
    try:
        while True:
            await websocket.receive_text()  # we ignore client messages; this notices disconnects
    except WebSocketDisconnect:
        pass
    finally:
        sender.cancel()
        event_bus.unsubscribe(queue)


@router.websocket("/ws/dashboard")
async def dashboard_socket(websocket: WebSocket, db: DbSession) -> None:
    if await _authenticate(websocket, db, STAFF_ROLES) is not None:
        await _stream(websocket, lambda event: True)


@router.websocket("/ws/tourist")
async def tourist_socket(websocket: WebSocket, db: DbSession) -> None:
    user = await _authenticate(websocket, db, {Role.TOURIST})
    if user is None:
        return

    def own_incident(event: dict) -> bool:
        incident = event.get("incident")
        return isinstance(incident, dict) and incident.get("reporter_user_id") == user.id

    await _stream(websocket, own_incident)
