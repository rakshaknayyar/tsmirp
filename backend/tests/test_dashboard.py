"""Dashboard WebSocket: authentication, and live incident events (memory and Redis)."""

import os

import pytest
import redis
from starlette.websockets import WebSocketDisconnect

from app.core.config import settings
from app.models.user import Role
from tests.conftest import app_client, auth_headers

REPORT = {"description": "Someone is following me near the fort", "category_code": "harassment"}


def _token(client, user) -> str:
    return auth_headers(client, user)["Authorization"].removeprefix("Bearer ")


def _check_live_events(client, users) -> None:
    tourist = auth_headers(client, users[Role.TOURIST])
    operator = auth_headers(client, users[Role.OPERATOR])

    with client.websocket_connect("/ws/dashboard") as ws:
        ws.send_json({"type": "auth", "token": _token(client, users[Role.OPERATOR])})
        assert ws.receive_json()["type"] == "ready"

        incident_id = client.post("/incidents", headers=tourist, json=REPORT).json()["id"]
        created = ws.receive_json()

        client.patch(
            f"/incidents/{incident_id}/status", headers=operator, json={"status": "ACKNOWLEDGED"}
        )
        changed = ws.receive_json()

    assert created["type"] == "incident.created"
    assert created["incident"]["id"] == incident_id
    assert created["incident"]["category"]["code"] == "harassment"
    assert changed["type"] == "incident.status_changed"
    assert changed["incident"]["status"] == "ACKNOWLEDGED"


def test_staff_receive_live_events(client, users):
    _check_live_events(client, users)


def test_tourist_is_disconnected(client, users):
    with client.websocket_connect("/ws/dashboard") as ws:
        ws.send_json({"type": "auth", "token": _token(client, users[Role.TOURIST])})
        with pytest.raises(WebSocketDisconnect) as closed:
            ws.receive_json()

    assert closed.value.code == 1008


def test_bad_token_is_disconnected(client):
    with client.websocket_connect("/ws/dashboard") as ws:
        ws.send_json({"type": "auth", "token": "not-a-real-token"})
        with pytest.raises(WebSocketDisconnect) as closed:
            ws.receive_json()

    assert closed.value.code == 1008


def test_live_events_through_redis(db, users, monkeypatch):
    try:
        redis.Redis.from_url(settings.redis_url, socket_connect_timeout=1).ping()
    except redis.RedisError:
        if os.getenv("REQUIRE_REDIS") == "1":
            pytest.fail("Redis not reachable")
        pytest.skip("Redis not running locally (this test runs in CI)")

    monkeypatch.setattr(settings, "event_backend", "redis")
    with app_client(db) as client:
        _check_live_events(client, users)
