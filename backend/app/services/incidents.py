"""Incident logic: creation, the status lifecycle, and who may see a location.

Status lifecycle (the only allowed moves):

    NEW -> ACKNOWLEDGED -> ASSIGNED -> EN_ROUTE -> RESOLVED -> CLOSED
                 |             |                     |
                 +-> RESOLVED  +-> RESOLVED          +-> ACKNOWLEDGED (re-open)

Severity in Phase 2 is a PROVISIONAL default (MEDIUM). The real severity rules arrive in
Phase 6; operators will be able to override them.
"""

from datetime import UTC, datetime, timedelta

from geoalchemy2 import WKTElement
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.incident import (
    Incident,
    IncidentCategory,
    IncidentLocation,
    IncidentStatus,
    Severity,
)
from app.models.tourist import TouristProfile
from app.models.user import User
from app.schemas.incident import CategoryOut, IncidentCreate, IncidentOut, LocationOut

S = IncidentStatus
ALLOWED_TRANSITIONS: dict[IncidentStatus, set[IncidentStatus]] = {
    S.NEW: {S.ACKNOWLEDGED},
    S.ACKNOWLEDGED: {S.ASSIGNED, S.RESOLVED},
    S.ASSIGNED: {S.EN_ROUTE, S.RESOLVED},
    S.EN_ROUTE: {S.RESOLVED},
    S.RESOLVED: {S.CLOSED, S.ACKNOWLEDGED},
    S.CLOSED: set(),
}

# ASSIGNED needs a resource, so it is set by the assign endpoint (Phase 3), not by hand.
NOT_SETTABLE_BY_STATUS_ENDPOINT = {S.ASSIGNED}


class InvalidTransition(Exception):
    pass


class UnknownCategory(Exception):
    pass


def change_status(
    incident: Incident, new_status: IncidentStatus, *, by_assignment: bool = False
) -> IncidentStatus:
    """Move the incident to new_status if the lifecycle allows it. Returns the old status.
    by_assignment=True is used only by the assign service (app/services/resources.py)."""
    old_status = incident.status
    if new_status in NOT_SETTABLE_BY_STATUS_ENDPOINT and not by_assignment:
        raise InvalidTransition(f"{new_status} is set by assigning a resource, not directly")
    if new_status not in ALLOWED_TRANSITIONS[old_status]:
        raise InvalidTransition(f"Cannot move an incident from {old_status} to {new_status}")
    incident.status = new_status
    return old_status


def create_incident(db: Session, reporter: User, body: IncidentCreate) -> Incident:
    """Store a tourist's report (and its location, if given). The caller audits and commits."""
    category_id = None
    if body.category_code is not None:
        category_id = db.scalar(
            select(IncidentCategory.id).where(IncidentCategory.code == body.category_code)
        )
        if category_id is None:
            raise UnknownCategory(body.category_code)

    incident = Incident(
        reporter_user_id=reporter.id,
        category_id=category_id,
        description=body.description,
        language=body.language,
        severity=Severity.MEDIUM,  # provisional until the Phase 6 severity rules
        status=IncidentStatus.NEW,
        is_sos=False,
    )
    db.add(incident)
    db.flush()

    if body.location is not None:
        add_incident_location(
            db, incident, body.location.lat, body.location.lon, body.location.accuracy_m
        )
    return incident


def add_incident_location(
    db: Session, incident: Incident, lat: float, lon: float, accuracy_m: float | None
) -> None:
    now = datetime.now(UTC)
    db.add(
        IncidentLocation(
            incident_id=incident.id,
            # WKT text "POINT(lon lat)": longitude comes first in PostGIS.
            geom=WKTElement(f"POINT({lon} {lat})", srid=4326),
            accuracy_m=accuracy_m,
            recorded_at=now,
            expires_at=now + timedelta(days=settings.location_retention_days),
        )
    )
    db.flush()


def _may_see_location(db: Session, incident: Incident, viewer: User | None) -> bool:
    """The reporter always sees their own location. Staff see it only during an SOS or
    while the reporter's location consent is still switched on."""
    if viewer is not None and viewer.id == incident.reporter_user_id:
        return True
    if incident.is_sos:
        return True
    consent = db.scalar(
        select(TouristProfile.location_consent).where(
            TouristProfile.user_id == incident.reporter_user_id
        )
    )
    return bool(consent)


def _latest_location(db: Session, incident_id: int) -> LocationOut | None:
    row = db.execute(
        select(
            func.ST_Y(IncidentLocation.geom),  # latitude
            func.ST_X(IncidentLocation.geom),  # longitude
            IncidentLocation.accuracy_m,
            IncidentLocation.recorded_at,
        )
        .where(
            IncidentLocation.incident_id == incident_id,
            IncidentLocation.expires_at > func.now(),  # expired locations are never shown
        )
        .order_by(IncidentLocation.recorded_at.desc())
        .limit(1)
    ).first()
    if row is None:
        return None
    lat, lon, accuracy_m, recorded_at = row
    return LocationOut(lat=lat, lon=lon, accuracy_m=accuracy_m, recorded_at=recorded_at)


def to_incident_out(db: Session, incident: Incident, viewer: User | None) -> IncidentOut:
    """Build the API response. viewer=None means "staff broadcast" (dashboard event)."""
    category = db.get(IncidentCategory, incident.category_id) if incident.category_id else None
    location = None
    if _may_see_location(db, incident, viewer):
        location = _latest_location(db, incident.id)
    return IncidentOut(
        id=incident.id,
        reporter_user_id=incident.reporter_user_id,
        category=CategoryOut.model_validate(category) if category else None,
        description=incident.description,
        language=incident.language,
        severity=incident.severity,
        status=incident.status,
        is_sos=incident.is_sos,
        confidence=incident.confidence,
        created_at=incident.created_at,
        updated_at=incident.updated_at,
        location=location,
    )
