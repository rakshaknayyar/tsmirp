"""Incident API: reporting, visibility rules, location consent, and status changes."""

from sqlalchemy import func, select

from app.models.audit import AuditLog
from app.models.incident import IncidentLocation
from app.models.user import Role
from tests.conftest import auth_headers, make_user

REPORT = {"description": "My phone was stolen near the market", "category_code": "theft"}
LOCATION = {"lat": 26.9124, "lon": 75.7873, "accuracy_m": 15}  # example point (Jaipur)


def _report(client, headers, **overrides):
    return client.post("/incidents", headers=headers, json={**REPORT, **overrides})


def _grant_consent(client, headers):
    client.put("/tourist/consent", headers=headers, json={"location_consent": True})


def test_nine_categories_with_departments(client, users):
    headers = auth_headers(client, users[Role.TOURIST])

    categories = client.get("/incident-categories", headers=headers).json()

    assert len(categories) == 9
    by_code = {c["code"]: c["department"] for c in categories}
    assert by_code["theft"] == "Police"
    assert by_code["fire"] == "Fire"


def test_tourist_reports_incident(client, users):
    headers = auth_headers(client, users[Role.TOURIST])

    response = _report(client, headers)

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "NEW"
    assert body["severity"] == "MEDIUM"  # provisional until Phase 6
    assert body["category"]["department"] == "Police"
    assert body["is_sos"] is False
    assert body["location"] is None


def test_unknown_category_is_rejected(client, users):
    headers = auth_headers(client, users[Role.TOURIST])

    assert _report(client, headers, category_code="alien_abduction").status_code == 422


def test_tourist_cannot_set_severity_or_status(client, users):
    headers = auth_headers(client, users[Role.TOURIST])

    assert _report(client, headers, severity="LOW").status_code == 422
    assert _report(client, headers, status="CLOSED").status_code == 422


def test_staff_cannot_report_as_tourist(client, users):
    headers = auth_headers(client, users[Role.OPERATOR])

    assert _report(client, headers).status_code == 403


def test_location_requires_consent(client, users):
    headers = auth_headers(client, users[Role.TOURIST])

    response = _report(client, headers, location=LOCATION)

    assert response.status_code == 403


def test_location_is_stored_as_lon_lat_point(client, db, users):
    headers = auth_headers(client, users[Role.TOURIST])
    _grant_consent(client, headers)

    body = _report(client, headers, location=LOCATION).json()

    assert body["location"]["lat"] == LOCATION["lat"]
    assert body["location"]["lon"] == LOCATION["lon"]
    x, y = db.execute(
        select(func.ST_X(IncidentLocation.geom), func.ST_Y(IncidentLocation.geom)).where(
            IncidentLocation.incident_id == body["id"]
        )
    ).one()
    assert (x, y) == (LOCATION["lon"], LOCATION["lat"])  # PostGIS: x = longitude


def test_staff_see_location_only_while_consent_is_on(client, users):
    tourist_headers = auth_headers(client, users[Role.TOURIST])
    operator_headers = auth_headers(client, users[Role.OPERATOR])
    _grant_consent(client, tourist_headers)
    incident_id = _report(client, tourist_headers, location=LOCATION).json()["id"]

    seen_with_consent = client.get(f"/incidents/{incident_id}", headers=operator_headers).json()
    client.put("/tourist/consent", headers=tourist_headers, json={"location_consent": False})
    seen_after_revoke = client.get(f"/incidents/{incident_id}", headers=operator_headers).json()
    reporter_view = client.get(f"/incidents/{incident_id}", headers=tourist_headers).json()

    assert seen_with_consent["location"] is not None
    assert seen_after_revoke["location"] is None
    assert reporter_view["location"] is not None  # tourists always see their own


def test_tourists_only_see_their_own_incidents(client, db):
    alice = auth_headers(client, make_user(db, Role.TOURIST, name="alice"))
    bob = auth_headers(client, make_user(db, Role.TOURIST, name="bob"))
    alice_incident = _report(client, alice).json()["id"]

    assert client.get("/incidents", headers=bob).json() == []
    assert client.get(f"/incidents/{alice_incident}", headers=bob).status_code == 404
    assert [i["id"] for i in client.get("/incidents", headers=alice).json()] == [alice_incident]


def test_staff_see_all_incidents(client, db, users):
    alice = auth_headers(client, make_user(db, Role.TOURIST, name="alice"))
    bob = auth_headers(client, make_user(db, Role.TOURIST, name="bob"))
    ids = {_report(client, alice).json()["id"], _report(client, bob).json()["id"]}

    listed = client.get("/incidents", headers=auth_headers(client, users[Role.OPERATOR])).json()

    assert ids <= {i["id"] for i in listed}


def test_status_lifecycle_and_audit(client, db, users):
    incident_id = _report(client, auth_headers(client, users[Role.TOURIST])).json()["id"]
    operator = users[Role.OPERATOR]
    headers = auth_headers(client, operator)

    for new_status in ["ACKNOWLEDGED", "RESOLVED", "CLOSED"]:
        response = client.patch(
            f"/incidents/{incident_id}/status", headers=headers, json={"status": new_status}
        )
        assert response.status_code == 200
        assert response.json()["status"] == new_status

    audited = db.scalars(
        select(AuditLog.details).where(
            AuditLog.action == "incident.status_changed", AuditLog.target_id == str(incident_id)
        )
    ).all()
    assert [d["to"] for d in audited] == ["ACKNOWLEDGED", "RESOLVED", "CLOSED"]


def test_invalid_status_moves_are_refused(client, users):
    incident_id = _report(client, auth_headers(client, users[Role.TOURIST])).json()["id"]
    headers = auth_headers(client, users[Role.OPERATOR])
    url = f"/incidents/{incident_id}/status"

    skip_ahead = client.patch(url, headers=headers, json={"status": "RESOLVED"})
    assign_by_hand = client.patch(url, headers=headers, json={"status": "ASSIGNED"})

    assert skip_ahead.status_code == 409
    assert assign_by_hand.status_code == 409


def test_tourist_cannot_change_status(client, users):
    headers = auth_headers(client, users[Role.TOURIST])
    incident_id = _report(client, headers).json()["id"]

    response = client.patch(
        f"/incidents/{incident_id}/status", headers=headers, json={"status": "CLOSED"}
    )

    assert response.status_code == 403


def test_filter_by_status(client, users):
    tourist = auth_headers(client, users[Role.TOURIST])
    operator = auth_headers(client, users[Role.OPERATOR])
    first = _report(client, tourist).json()["id"]
    second = _report(client, tourist).json()["id"]
    client.patch(f"/incidents/{first}/status", headers=operator, json={"status": "ACKNOWLEDGED"})

    acknowledged = client.get("/incidents?status=ACKNOWLEDGED", headers=operator).json()

    ids = [i["id"] for i in acknowledged]
    assert first in ids
    assert second not in ids
