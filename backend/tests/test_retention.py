"""Phase 9: the retention job deletes expired locations, and nothing else."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select

from app.core.config import settings
from app.models.audit import AuditLog
from app.models.incident import Incident, IncidentLocation
from app.models.tourist import TouristProfile
from app.models.user import Role
from app.services.retention import purge_expired
from tests.conftest import auth_headers

FIX = {"lat": 26.92, "lon": 75.82, "accuracy_m": 10}


def _report_with_location(client, user) -> int:
    headers = auth_headers(client, user)
    client.put("/tourist/consent", headers=headers, json={"location_consent": True})
    client.post("/tourist/location", headers=headers, json=FIX)
    body = {"description": "Test report with a location", "location": FIX}
    return client.post("/incidents", headers=headers, json=body).json()["id"]


def _location_count(db, incident_id: int) -> int:
    return db.scalar(
        select(func.count())
        .select_from(IncidentLocation)
        .where(IncidentLocation.incident_id == incident_id)
    )


def test_nothing_is_deleted_before_expiry(client, db, users):
    incident_id = _report_with_location(client, users[Role.TOURIST])

    purge_expired(db, datetime.now(UTC))

    assert _location_count(db, incident_id) == 1
    profile = db.scalar(
        select(TouristProfile).where(TouristProfile.user_id == users[Role.TOURIST].id)
    )
    assert profile.last_location is not None


def test_expired_locations_are_deleted_and_incident_is_kept(client, db, users):
    incident_id = _report_with_location(client, users[Role.TOURIST])
    later = datetime.now(UTC) + timedelta(days=settings.location_retention_days, minutes=1)

    result = purge_expired(db, later)

    assert result.incident_locations_deleted >= 1
    assert result.tourist_locations_cleared >= 1
    assert _location_count(db, incident_id) == 0
    assert db.get(Incident, incident_id) is not None  # the report itself stays
    profile = db.scalar(
        select(TouristProfile).where(TouristProfile.user_id == users[Role.TOURIST].id)
    )
    assert profile.last_location is None and profile.last_location_at is None
    audit = db.scalar(select(AuditLog).where(AuditLog.action == "retention.purged"))
    assert audit.details["incident_locations_deleted"] == result.incident_locations_deleted
