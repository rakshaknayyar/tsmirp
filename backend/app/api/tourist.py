"""Tourist routes: own profile, location consent, emergency contacts, location sharing,
notifications - plus one staff route to view a tourist's location (consent / SOS only).

Object-level authorisation: every tourist query is filtered by the logged-in tourist's own
profile, so one tourist can never read or delete another tourist's data (they get 404).
"""

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy import exists, func, select
from sqlalchemy.orm import Session

from app.api.deps import DbSession, StaffUser, TouristUser
from app.models.incident import Incident, IncidentStatus
from app.models.notification import Notification
from app.models.risk import RiskZone
from app.models.tourist import EmergencyContact, TouristProfile
from app.models.user import User
from app.schemas.location import (
    FixResultOut,
    LocationFix,
    NotificationOut,
    TouristLocationOut,
    ZoneBrief,
)
from app.schemas.tourist import (
    ConsentUpdate,
    EmergencyContactCreate,
    EmergencyContactOut,
    ProfileOut,
    ProfileUpdate,
)
from app.services.audit import record_event
from app.services.events import event_bus
from app.services.geofence import clear_location, process_fix

router = APIRouter(prefix="/tourist", tags=["tourist"])


def _own_profile(user: User, db: Session) -> TouristProfile:
    profile = db.scalar(select(TouristProfile).where(TouristProfile.user_id == user.id))
    if profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tourist profile not found")
    return profile


def _zone_brief(zone: RiskZone, levels: dict) -> ZoneBrief:
    return ZoneBrief(
        id=zone.id, name=zone.name, level=levels[zone.id].level, is_synthetic=zone.is_synthetic
    )


@router.get("/profile", response_model=ProfileOut)
def get_profile(user: TouristUser, db: DbSession) -> TouristProfile:
    return _own_profile(user, db)


@router.put("/profile", response_model=ProfileOut)
def update_profile(body: ProfileUpdate, user: TouristUser, db: DbSession) -> TouristProfile:
    profile = _own_profile(user, db)
    profile.nationality = body.nationality
    profile.phone = body.phone
    profile.preferred_language = body.preferred_language
    db.commit()
    return profile


@router.put("/consent", response_model=ProfileOut)
def update_consent(body: ConsentUpdate, user: TouristUser, db: DbSession) -> TouristProfile:
    """Grant or revoke location consent. Every change is recorded in the audit log.
    Revoking also deletes the stored latest location straight away."""
    profile = _own_profile(user, db)
    if body.location_consent != profile.location_consent:
        profile.location_consent = body.location_consent
        profile.consent_time = datetime.now(UTC)
        if not body.location_consent:
            clear_location(profile)
        action = "consent.location_granted" if body.location_consent else "consent.location_revoked"
        record_event(
            db, action, actor_user_id=user.id, target_type="tourist_profile", target_id=profile.id
        )
        db.commit()
    return profile


@router.post("/location", response_model=FixResultOut)
def share_location(body: LocationFix, user: TouristUser, db: DbSession) -> FixResultOut:
    """Send one location fix. Requires consent. Runs the geofence check."""
    profile = _own_profile(user, db)
    if not profile.location_consent:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Turn on location consent before sharing your location"
        )
    result = process_fix(db, user, profile, body.lat, body.lon, body.accuracy_m, datetime.now(UTC))
    db.commit()

    for alert in result.alerts:
        event_bus.publish(
            {
                "type": "geofence.alert",
                "tourist_user_id": user.id,
                "zone": {
                    "id": alert.zone_id,
                    "name": next(z.name for z in result.inside if z.id == alert.zone_id),
                    "level": alert.payload["level"],
                },
                "at": datetime.now(UTC).isoformat(),
            }
        )
    return FixResultOut(
        accepted=result.accepted,
        reason=result.reason,
        inside_zones=[_zone_brief(z, result.levels) for z in result.inside],
        nearby_zones=[_zone_brief(z, result.levels) for z in result.nearby],
        alerts=[NotificationOut.model_validate(n) for n in result.alerts],
    )


@router.get("/notifications", response_model=list[NotificationOut])
def list_notifications(user: TouristUser, db: DbSession) -> list[Notification]:
    query = select(Notification).where(Notification.user_id == user.id)
    return list(db.scalars(query.order_by(Notification.id.desc()).limit(50)))


@router.get("/location/{tourist_user_id}", response_model=TouristLocationOut)
def view_tourist_location(
    tourist_user_id: int, staff: StaffUser, db: DbSession
) -> TouristLocationOut:
    """Staff only. Allowed while the tourist's consent is on, or while they have an active
    SOS. Every successful view is written to the audit log."""
    profile = db.scalar(select(TouristProfile).where(TouristProfile.user_id == tourist_user_id))
    if profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tourist not found")

    active_sos = db.scalar(
        select(
            exists().where(
                Incident.reporter_user_id == tourist_user_id,
                Incident.is_sos.is_(True),
                Incident.status.not_in([IncidentStatus.RESOLVED, IncidentStatus.CLOSED]),
            )
        )
    )
    if not profile.location_consent and not active_sos:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "No location consent and no active SOS for this tourist"
        )
    now = datetime.now(UTC)
    if profile.last_location is None or profile.last_location_expires_at <= now:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No current location for this tourist")

    lat, lon = db.execute(
        select(
            func.ST_Y(TouristProfile.last_location), func.ST_X(TouristProfile.last_location)
        ).where(TouristProfile.id == profile.id)
    ).one()
    basis = "consent" if profile.location_consent else "active_sos"
    record_event(
        db,
        "location.viewed",
        actor_user_id=staff.id,
        target_type="user",
        target_id=tourist_user_id,
        details={"basis": basis},
    )
    db.commit()
    return TouristLocationOut(
        user_id=tourist_user_id,
        lat=lat,
        lon=lon,
        accuracy_m=profile.last_location_accuracy_m,
        recorded_at=profile.last_location_at,
        basis=basis,
    )


@router.get("/emergency-contacts", response_model=list[EmergencyContactOut])
def list_contacts(user: TouristUser, db: DbSession) -> list[EmergencyContact]:
    profile = _own_profile(user, db)
    query = select(EmergencyContact).where(EmergencyContact.tourist_profile_id == profile.id)
    return list(db.scalars(query.order_by(EmergencyContact.id)))


@router.post(
    "/emergency-contacts",
    response_model=EmergencyContactOut,
    status_code=status.HTTP_201_CREATED,
)
def add_contact(body: EmergencyContactCreate, user: TouristUser, db: DbSession) -> EmergencyContact:
    profile = _own_profile(user, db)
    contact = EmergencyContact(tourist_profile_id=profile.id, **body.model_dump())
    db.add(contact)
    db.flush()
    record_event(
        db,
        "emergency_contact.added",
        actor_user_id=user.id,
        target_type="emergency_contact",
        target_id=contact.id,
    )
    db.commit()
    return contact


@router.delete("/emergency-contacts/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_contact(contact_id: int, user: TouristUser, db: DbSession) -> Response:
    profile = _own_profile(user, db)
    contact = db.scalar(
        select(EmergencyContact).where(
            EmergencyContact.id == contact_id,
            EmergencyContact.tourist_profile_id == profile.id,  # must belong to this tourist
        )
    )
    if contact is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Contact not found")
    db.delete(contact)
    record_event(
        db,
        "emergency_contact.deleted",
        actor_user_id=user.id,
        target_type="emergency_contact",
        target_id=contact_id,
    )
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
