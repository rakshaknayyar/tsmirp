"""SOS: trigger, sandbox notifications, location rules, cancel, rate limit, and live status
updates to the tourist."""

import pytest
from geoalchemy2 import WKTElement
from sqlalchemy import select
from starlette.websockets import WebSocketDisconnect

from app.core.rate_limit import sos_limiter
from app.models.audit import AuditLog
from app.models.notification import Notification, NotificationChannel
from app.models.resource import Availability, ResponseResource
from app.models.tourist import TouristProfile
from app.models.user import Role
from tests.conftest import auth_headers, make_user

SOS_LOCATION = {"lat": 11.0, "lon": 11.0, "accuracy_m": 12}


def _token(client, user) -> str:
    return auth_headers(client, user)["Authorization"].removeprefix("Bearer ")


def _add_contacts(client, headers, count=2):
    for i in range(count):
        client.post(
            "/tourist/emergency-contacts",
            headers=headers,
            json={"name": f"Contact {i}", "phone": f"+91 90000 0000{i}", "relation": "friend"},
        )


def _profile(db, user) -> TouristProfile:
    return db.scalar(select(TouristProfile).where(TouristProfile.user_id == user.id))


def test_sos_creates_critical_incident_and_sandbox_notifications(client, db, users):
    tourist = users[Role.TOURIST]
    headers = auth_headers(client, tourist)
    _add_contacts(client, headers, count=2)

    response = client.post("/sos", headers=headers, json={"location": SOS_LOCATION})

    assert response.status_code == 201
    body = response.json()
    incident = body["incident"]
    assert incident["is_sos"] is True
    assert incident["severity"] == "CRITICAL"
    assert incident["category"] is None  # SOS skips classification
    assert incident["location"]["lat"] == SOS_LOCATION["lat"]
    assert body["contacts_notified"] == 2
    assert "112" in body["advice"]

    sent = db.scalars(select(Notification).where(Notification.incident_id == incident["id"])).all()
    sms = [n for n in sent if n.channel == NotificationChannel.SMS_SANDBOX]
    assert len(sms) == 2
    assert all(n.simulated and n.body.startswith("[SIMULATED SMS - not sent]") for n in sms)
    assert {n.recipient for n in sms} == {"+91 90000 00000", "+91 90000 00001"}
    email = [n for n in sent if n.channel == NotificationChannel.EMAIL_SANDBOX]
    assert len(email) == 1 and email[0].recipient == tourist.email
    in_app = [n for n in sent if n.channel == NotificationChannel.IN_APP]
    assert "112" in in_app[0].body and "1363" in in_app[0].body
    assert db.scalar(select(AuditLog).where(AuditLog.action == "sos.triggered"))


def test_second_sos_returns_the_open_one(client, users):
    headers = auth_headers(client, users[Role.TOURIST])

    first = client.post("/sos", headers=headers, json={})
    second = client.post("/sos", headers=headers, json={})

    assert (first.status_code, second.status_code) == (201, 200)
    assert second.json()["created"] is False
    assert second.json()["incident"]["id"] == first.json()["incident"]["id"]


def test_sos_without_consent_shares_location_for_this_emergency_only(client, db, users):
    tourist = users[Role.TOURIST]
    tourist_headers = auth_headers(client, tourist)
    operator_headers = auth_headers(client, users[Role.OPERATOR])

    incident_id = client.post(
        "/sos", headers=tourist_headers, json={"location": SOS_LOCATION}
    ).json()["incident"]["id"]

    # Consent is off, but during the SOS staff may see the location.
    seen = client.get(f"/incidents/{incident_id}", headers=operator_headers).json()
    followed = client.get(f"/tourist/location/{tourist.id}", headers=operator_headers)
    assert seen["location"] is not None
    assert followed.status_code == 200
    assert followed.json()["basis"] == "active_sos"

    # After the SOS ends, the emergency-only location is deleted again.
    client.post(f"/sos/{incident_id}/cancel", headers=tourist_headers)
    db.expire_all()
    assert _profile(db, tourist).last_location is None
    after = client.get(f"/tourist/location/{tourist.id}", headers=operator_headers)
    assert after.status_code == 403


def test_sos_uses_recent_shared_location_when_none_is_sent(client, users):
    headers = auth_headers(client, users[Role.TOURIST])
    client.put("/tourist/consent", headers=headers, json={"location_consent": True})
    client.post("/tourist/location", headers=headers, json=SOS_LOCATION)

    body = client.post("/sos", headers=headers, json={}).json()

    assert body["incident"]["location"]["lat"] == SOS_LOCATION["lat"]


def test_sos_returns_nearest_help(client, db, users):
    station = ResponseResource(
        name="SOS test station",
        resource_type="police_station",
        geog=WKTElement("POINT(11.001 11.0)", srid=4326),
        source="manual",
        capabilities=[],
        availability_sim=Availability.AVAILABLE,
    )
    db.add(station)
    db.commit()
    headers = auth_headers(client, users[Role.TOURIST])

    body = client.post("/sos", headers=headers, json={"location": SOS_LOCATION}).json()

    assert body["nearest_help"][0]["id"] == station.id
    assert body["nearest_help"][0]["distance_kind"] == "straight_line"


def test_staff_cannot_trigger_sos(client, users):
    response = client.post("/sos", headers=auth_headers(client, users[Role.OPERATOR]), json={})

    assert response.status_code == 403


def test_cancel_only_own_open_sos(client, db, users):
    owner = auth_headers(client, users[Role.TOURIST])
    other = auth_headers(client, make_user(db, Role.TOURIST, name="other"))
    _add_contacts(client, owner, count=1)
    incident_id = client.post("/sos", headers=owner, json={}).json()["incident"]["id"]

    by_other = client.post(f"/sos/{incident_id}/cancel", headers=other)
    by_owner = client.post(f"/sos/{incident_id}/cancel", headers=owner)
    again = client.post(f"/sos/{incident_id}/cancel", headers=owner)

    assert by_other.status_code == 404
    assert by_owner.status_code == 200
    assert by_owner.json()["incident"]["status"] == "RESOLVED"
    assert again.status_code == 409
    cancelled_sms = db.scalars(
        select(Notification).where(
            Notification.incident_id == incident_id, Notification.kind == "sos_cancelled"
        )
    ).all()
    assert len(cancelled_sms) == 1


def test_sos_is_rate_limited(client, users, monkeypatch):
    monkeypatch.setattr(sos_limiter, "max_requests", 2)
    headers = auth_headers(client, users[Role.TOURIST])

    statuses = []
    for _ in range(3):
        response = client.post("/sos", headers=headers, json={})
        statuses.append(response.status_code)
        if response.status_code == 201:
            client.post(f"/sos/{response.json()['incident']['id']}/cancel", headers=headers)

    assert statuses == [201, 201, 429]
    assert "112" in response.json()["detail"]


def test_status_changes_notify_the_tourist(client, db, users):
    tourist = users[Role.TOURIST]
    tourist_headers = auth_headers(client, tourist)
    operator_headers = auth_headers(client, users[Role.OPERATOR])
    incident_id = client.post("/sos", headers=tourist_headers, json={}).json()["incident"]["id"]

    client.patch(
        f"/incidents/{incident_id}/status",
        headers=operator_headers,
        json={"status": "ACKNOWLEDGED"},
    )

    titles = [
        n["title"] for n in client.get("/tourist/notifications", headers=tourist_headers).json()
    ]
    assert f"Update on your SOS #{incident_id}: ACKNOWLEDGED" in titles


# ---------- live updates over /ws/tourist ----------


def test_tourist_socket_gets_only_own_incident_updates(client, db, users):
    tourist = users[Role.TOURIST]
    other = make_user(db, Role.TOURIST, name="other")
    tourist_headers = auth_headers(client, tourist)
    other_headers = auth_headers(client, other)
    operator_headers = auth_headers(client, users[Role.OPERATOR])

    with client.websocket_connect("/ws/tourist") as ws:
        ws.send_json({"type": "auth", "token": _token(client, tourist)})
        assert ws.receive_json()["type"] == "ready"

        # Another tourist's SOS must NOT reach this socket ...
        client.post("/sos", headers=other_headers, json={})
        # ... but this tourist's own SOS and its status change must.
        own_id = client.post("/sos", headers=tourist_headers, json={}).json()["incident"]["id"]
        created = ws.receive_json()
        client.patch(
            f"/incidents/{own_id}/status", headers=operator_headers, json={"status": "ACKNOWLEDGED"}
        )
        changed = ws.receive_json()

    assert created["type"] == "incident.created" and created["incident"]["id"] == own_id
    assert changed["incident"]["status"] == "ACKNOWLEDGED"


def test_staff_cannot_use_tourist_socket(client, users):
    with client.websocket_connect("/ws/tourist") as ws:
        ws.send_json({"type": "auth", "token": _token(client, users[Role.OPERATOR])})
        with pytest.raises(WebSocketDisconnect) as closed:
            ws.receive_json()

    assert closed.value.code == 1008
