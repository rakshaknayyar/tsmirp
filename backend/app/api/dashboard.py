"""WS /ws/dashboard - live incident events for staff.

Protocol:
1. Client connects.
2. Within 5 seconds the client sends: {"type": "auth", "token": "<access token>"}.
   (The token is sent as a message, not in the URL, so it never appears in server logs.)
3. Server replies {"type": "ready", "mode": "redis" | "memory"} and then pushes events:
   {"type": "incident.created" | "incident.status_changed", "incident": {...}}
Non-staff users or bad tokens are disconnected with close code 1008 (policy violation).
"""

import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
from starlette.concurrency import run_in_threadpool

from app.api.deps import DbSession, user_from_access_token
from app.models.user import STAFF_ROLES
from app.services.events import event_bus

router = APIRouter(tags=["dashboard"])

AUTH_TIMEOUT_SECONDS = 5


@router.websocket("/ws/dashboard")
async def dashboard_socket(websocket: WebSocket, db: DbSession) -> None:
    await websocket.accept()
    try:
        first = await asyncio.wait_for(websocket.receive_json(), AUTH_TIMEOUT_SECONDS)
    except (TimeoutError, ValueError, WebSocketDisconnect):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    token = first.get("token") if isinstance(first, dict) and first.get("type") == "auth" else None
    # Database calls are blocking, so run them in a worker thread.
    user = await run_in_threadpool(user_from_access_token, db, token)
    if user is None or user.role not in STAFF_ROLES:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    queue = event_bus.subscribe()
    await websocket.send_json({"type": "ready", "mode": event_bus.mode})

    async def forward_events() -> None:
        while True:
            await websocket.send_json(await queue.get())

    sender = asyncio.create_task(forward_events())
    try:
        while True:
            await websocket.receive_text()  # we ignore client messages; this notices disconnects
    except WebSocketDisconnect:
        pass
    finally:
        sender.cancel()
        event_bus.unsubscribe(queue)
