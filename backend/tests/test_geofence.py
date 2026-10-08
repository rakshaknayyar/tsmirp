"""Geofencing: consent, accuracy filter, zone detection, dwell/debounce, and who may see a
tourist's location.

Test zones are circles around 12 N, 12 E, far from the Jaipur demo zones.
"""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select

from app.core.config import settings
from app.models.audit import AuditLog
from app.models.incident import Incident, IncidentStatus, Severity
from app.models.notification import Notification
from app.models.risk import RiskLevel, RiskZone
from app.models.tourist import TouristProfile
from app.models.user import Role
from app.services.geo import geography_point
from app.services.geofence import process_fix
from tests.conftest import auth_headers

LAT, LON = 12.0, 12.0
INSIDE = {"lat": LAT, "lon": LON, "accuracy_m": 20}
OUTSIDE = {"lat": LAT + 0.05, "lon": LON, "accuracy_m": 20}  # about 5.5 km north


def add_zone(db, name, level, lat=LAT, lon=LON, radius_m=300) -> RiskZone:
    zone = RiskZone(
        name=name,
        geom=func.geometry(func.ST_Buffer(geography_point(lat, lon), radius_m)),
        base_level=level,
        is_synthetic=True,
        source="test",
    )
    db.add(zone)
    db.flush()
    return zone


def _profile(db, user) -> TouristProfile:
    return db.scalar(select(TouristProfile).where(TouristProfile.user_id == user.id))


def _consent(client, headers, value=True):
    client.put("/tourist/consent", headers=headers, json={"location_consent": value})


@pytest.fixture
def no_dwell(monkeypatch):
    """Alert on the first fix inside a zone (makes API-level tests simple)."""
    monkeypatch.setattr(settings, "geofence_dwell_seconds", 0)


# ---------- sharing a location ----------


def test_location_needs_consent(client, users):
    headers = auth_headers(client, users[Role.TOURIST])

    response = client.post("/tourist/location", headers=headers, json=INSIDE)

    assert response.status_code == 403


def test_inaccurate_fix_is_ignored_and_not_stored(client, db, users):
    tourist = users[Role.TOURIST]
    headers = auth_headers(client, tourist)
    _consent(client, headers)

    body = client.post(
        "/tourist/location", headers=headers, json={"lat": LAT, "lon": LON, "accuracy_m": 500}
    ).json()

    assert body["accepted"] is False
    assert "accuracy" in body["reason"]
    db.expire_all()
    assert _profile(db, tourist).last_location is None


def test_high_zone_alerts_and_is_audited(client, db, users, no_dwell):
    zone = add_zone(db, "Test high zone", RiskLevel.HIGH)
    db.commit()
    tourist = users[Role.TOURIST]
    headers = auth_headers(client, tourist)
    _consent(client, headers)

    body = client.post("/tourist/location", headers=headers, json=INSIDE).json()

    assert body["accepted"] is True
    assert [z["id"] for z in body["inside_zones"]] == [zone.id]
    assert len(body["alerts"]) == 1
    assert "112" in body["alerts"][0]["body"] and "1363" in body["alerts"][0]["body"]
    listed = client.get("/tourist/notifications", headers=headers).json()
    assert listed[0]["kind"] == "geofence_alert"
    audit = db.scalar(select(AuditLog).where(AuditLog.action == "geofence.alert"))
    assert audit.target_id == str(zone.id)
    assert "lat" not in audit.details  # no coordinates in the audit log


def test_low_and_moderate_zones_never_alert(client, db, users, no_dwell):
    add_zone(db, "Test low zone", RiskLevel.LOW)
    add_zone(db, "Test moderate zone", RiskLevel.MODERATE, radius_m=500)
    db.commit()
    headers = auth_headers(client, users[Role.TOURIST])
    _consent(client, headers)

    body = client.post("/tourist/location", headers=headers, json=INSIDE).json()

    assert len(body["inside_zones"]) == 2
    assert body["alerts"] == []


def test_nearby_zone_is_reported_without_alert(client, db, users, no_dwell):
    # Zone centred ~400 m north, radius 300 m: the point is ~100 m outside its edge.
    zone = add_zone(db, "Test nearby zone", RiskLevel.CRITICAL, lat=LAT + 0.0036)
    db.commit()
    headers = auth_headers(client, users[Role.TOURIST])
    _consent(client, headers)

    body = client.post("/tourist/location", headers=headers, json=INSIDE).json()

    assert body["inside_zones"] == []
    assert [z["id"] for z in body["nearby_zones"]] == [zone.id]
    assert body["alerts"] == []


# ---------- dwell and debounce (service level, simulated clock) ----------


def test_dwell_and_debounce(db, users, monkeypatch):
    monkeypatch.setattr(settings, "geofence_dwell_seconds", 60)
    monkeypatch.setattr(settings, "geofence_cooldown_seconds", 600)
    add_zone(db, "Test critical zone", RiskLevel.CRITICAL)
    tourist = users[Role.TOURIST]
    profile = _profile(db, tourist)
    t0 = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)

    def fix(seconds: int, where: dict) -> int:
        result = process_fix(
            db, tourist, profile, where["lat"], where["lon"], 20, t0 + timedelta(seconds=seconds)
        )
        return len(result.alerts)

    assert fix(0, INSIDE) == 0  # just entered
    assert fix(30, INSIDE) == 0  # not long enough yet
    assert fix(61, INSIDE) == 1  # dwelled 61 s -> one alert
    assert fix(90, INSIDE) == 0  # still inside: no repeat
    assert fix(100, OUTSIDE) == 0  # left
    assert fix(200, INSIDE) == 0  # back in: dwell restarts
    assert fix(300, INSIDE) == 0  # dwelled, but still within the 10 min cooldown
    assert fix(700, OUTSIDE) == 0  # cooldown over
    assert fix(800, INSIDE) == 0  # fresh entry
    assert fix(870, INSIDE) == 1  # dwelled again -> new alert


# ---------- consent revoke and staff access ----------


def test_revoking_consent_deletes_the_location(client, db, users):
    tourist = users[Role.TOURIST]
    headers = auth_headers(client, tourist)
    _consent(client, headers)
    client.post("/tourist/location", headers=headers, json=INSIDE)

    _consent(client, headers, value=False)

    db.expire_all()
    profile = _profile(db, tourist)
    assert profile.last_location is None
    assert profile.geofence_state == {}


def test_staff_can_view_location_with_consent_and_it_is_audited(client, db, users):
    tourist = users[Role.TOURIST]
    tourist_headers = auth_headers(client, tourist)
    operator_headers = auth_headers(client, users[Role.OPERATOR])
    _consent(client, tourist_headers)
    client.post("/tourist/location", headers=tourist_headers, json=INSIDE)

    response = client.get(f"/tourist/location/{tourist.id}", headers=operator_headers)

    assert response.status_code == 200
    body = response.json()
    assert (body["lat"], body["lon"], body["basis"]) == (LAT, LON, "consent")
    assert db.scalar(
        select(AuditLog).where(
            AuditLog.action == "location.viewed", AuditLog.target_id == str(tourist.id)
        )
    )


def test_staff_cannot_view_location_after_revoke(client, users):
    tourist = users[Role.TOURIST]
    tourist_headers = auth_headers(client, tourist)
    _consent(client, tourist_headers)
    client.post("/tourist/location", headers=tourist_headers, json=INSIDE)
    _consent(client, tourist_headers, value=False)

    response = client.get(
        f"/tourist/location/{tourist.id}", headers=auth_headers(client, users[Role.OPERATOR])
    )

    assert response.status_code == 403


def test_active_sos_allows_viewing_without_consent(client, db, users):
    tourist = users[Role.TOURIST]
    tourist_headers = auth_headers(client, tourist)
    operator_headers = auth_headers(client, users[Role.OPERATOR])
    _consent(client, tourist_headers)
    client.post("/tourist/location", headers=tourist_headers, json=INSIDE)
    # Simulate: consent switched off in the database, but an SOS is active (Phase 5 flow).
    profile = _profile(db, tourist)
    profile.location_consent = False
    sos = Incident(
        reporter_user_id=tourist.id,
        description="SOS",
        severity=Severity.CRITICAL,
        status=IncidentStatus.NEW,
        is_sos=True,
    )
    db.add(sos)
    db.commit()

    during_sos = client.get(f"/tourist/location/{tourist.id}", headers=operator_headers)
    sos.status = IncidentStatus.CLOSED
    db.commit()
    after_sos = client.get(f"/tourist/location/{tourist.id}", headers=operator_headers)

    assert during_sos.status_code == 200
    assert during_sos.json()["basis"] == "active_sos"
    assert after_sos.status_code == 403


def test_expired_location_is_not_shown(client, db, users):
    tourist = users[Role.TOURIST]
    tourist_headers = auth_headers(client, tourist)
    _consent(client, tourist_headers)
    client.post("/tourist/location", headers=tourist_headers, json=INSIDE)
    profile = _profile(db, tourist)
    profile.last_location_expires_at = datetime.now(UTC) - timedelta(seconds=1)
    db.commit()

    response = client.get(
        f"/tourist/location/{tourist.id}", headers=auth_headers(client, users[Role.OPERATOR])
    )

    assert response.status_code == 404


def test_tourist_cannot_view_other_locations(client, users):
    headers = auth_headers(client, users[Role.TOURIST])

    response = client.get(f"/tourist/location/{users[Role.TOURIST].id}", headers=headers)

    assert response.status_code == 403


def test_notifications_are_private(client, db, users, no_dwell):
    add_zone(db, "Test high zone", RiskLevel.HIGH)
    db.commit()
    tourist_headers = auth_headers(client, users[Role.TOURIST])
    _consent(client, tourist_headers)
    client.post("/tourist/location", headers=tourist_headers, json=INSIDE)

    operator_list = client.get(
        "/tourist/notifications", headers=auth_headers(client, users[Role.OPERATOR])
    )

    assert operator_list.status_code == 403
    assert db.scalar(select(func.count()).select_from(Notification)) >= 1
