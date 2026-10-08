"""Incident logic: creation (with automatic classification and severity rules), the status
lifecycle, and who may see a location.

Status lifecycle (the only allowed moves):

    NEW -> ACKNOWLEDGED -> ASSIGNED -> EN_ROUTE -> RESOLVED -> CLOSED
                 |             |                     |
                 +-> RESOLVED  +-> RESOLVED          +-> ACKNOWLEDGED (re-open)

Category: the tourist's own choice if given; otherwise the text classifier's suggestion
(with its confidence); if no model is available, unknown (flagged for review).
Severity: rule-based (app/services/severity.py). Operators can override both.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from geoalchemy2 import WKTElement
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.ml.text_classifier import ModelUnavailable
from app.models.incident import (
    Incident,
    IncidentCategory,
    IncidentLocation,
    IncidentStatus,
)
from app.models.risk import ALERT_LEVELS
from app.models.tourist import TouristProfile
from app.models.user import User
from app.schemas.incident import CategoryOut, IncidentCreate, IncidentOut, LocationOut
from app.services.classification import classify_text
from app.services.geofence import zones_containing
from app.services.severity import SeverityAssessment, assess_severity

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


@dataclass
class CreatedIncident:
    incident: Incident
    severity: SeverityAssessment
    classified_automatically: bool
    model_version: str | None


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


def category_by_code(db: Session, code: str) -> IncidentCategory:
    category = db.scalar(select(IncidentCategory).where(IncidentCategory.code == code))
    if category is None:
        raise UnknownCategory(code)
    return category


def in_high_risk_zone(db: Session, lat: float, lon: float) -> bool:
    return any(zone.base_level in ALERT_LEVELS for zone in zones_containing(db, lat, lon))


def create_incident(db: Session, reporter: User, body: IncidentCreate) -> CreatedIncident:
    """Store a tourist's report (and its location, if given). The caller audits and commits."""
    category: IncidentCategory | None = None
    confidence: float | None = None
    model_version: str | None = None
    if body.category_code is not None:
        category = category_by_code(db, body.category_code)  # chosen by the tourist
    else:
        try:
            result = classify_text(db, body.description, body.language)
            category, confidence, model_version = (
                result.category,
                result.confidence,
                result.model_version,
            )
        except ModelUnavailable:
            pass  # stays uncategorised and is flagged for review

    high_zone = body.location is not None and in_high_risk_zone(
        db, body.location.lat, body.location.lon
    )
    severity = assess_severity(
        body.description, category.code if category else None, in_high_risk_zone=high_zone
    )
    incident = Incident(
        reporter_user_id=reporter.id,
        category_id=category.id if category else None,
        description=body.description,
        language=body.language,
        severity=severity.severity,
        status=IncidentStatus.NEW,
        is_sos=False,
        confidence=confidence,
    )
    db.add(incident)
    db.flush()

    if body.location is not None:
        add_incident_location(
            db, incident, body.location.lat, body.location.lon, body.location.accuracy_m
        )
    return CreatedIncident(incident, severity, body.category_code is None, model_version)


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


def needs_review(incident: Incident) -> bool:
    """An operator should check the category: unknown, or a low-confidence suggestion.
    (SOS never needs a category.)"""
    if incident.is_sos:
        return False
    if incident.category_id is None:
        return True
    return incident.confidence is not None and (
        incident.confidence < settings.classify_review_threshold
    )


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
        needs_review=needs_review(incident),
        created_at=incident.created_at,
        updated_at=incident.updated_at,
        location=location,
    )
