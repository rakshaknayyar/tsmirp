"""SOS: trigger, cancel ("I'm safe"), and clean-up when an SOS ends.

Flow (the 5-second cancel window happens in the app BEFORE this is called):
1. If the tourist already has an open SOS, return it instead of creating a second one.
2. Location: the one sent with the SOS; otherwise the tourist's last shared location if it is
   recent and consent is on; otherwise none. Pressing SOS is explicit consent to share the
   location for THIS emergency, so it is stored on the incident and as the latest location.
3. Create a CRITICAL incident with is_sos=True and no category (SOS skips classification).
4. Sandbox SMS to every emergency contact, sandbox e-mail + in-app notice to the tourist.
5. Audit. (The route then publishes the event to the dashboard.)
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

from geoalchemy2 import WKTElement
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.incident import Incident, IncidentStatus, Severity
from app.models.tourist import EmergencyContact, TouristProfile
from app.models.user import User
from app.services.audit import record_event
from app.services.geofence import clear_location
from app.services.incidents import InvalidTransition, add_incident_location
from app.services.notifier import notify_in_app, sandbox_email, sandbox_sms
from app.services.resources import release_assignments

DEFAULT_DESCRIPTION = "SOS - emergency assistance requested"
FINISHED = (IncidentStatus.RESOLVED, IncidentStatus.CLOSED)


@dataclass
class SosResult:
    incident: Incident
    created: bool
    contacts_notified: int
    lat: float | None
    lon: float | None


def active_sos(db: Session, user_id: int) -> Incident | None:
    return db.scalar(
        select(Incident)
        .where(
            Incident.reporter_user_id == user_id,
            Incident.is_sos.is_(True),
            Incident.status.not_in(FINISHED),
        )
        .order_by(Incident.id.desc())
        .limit(1)
    )


def _recent_shared_location(
    db: Session, profile: TouristProfile, now: datetime
) -> tuple[float, float, float | None] | None:
    max_age = timedelta(seconds=settings.sos_last_location_max_age_seconds)
    if (
        not profile.location_consent
        or profile.last_location is None
        or profile.last_location_at is None
        or now - profile.last_location_at > max_age
    ):
        return None
    lat, lon = db.execute(
        select(
            func.ST_Y(TouristProfile.last_location), func.ST_X(TouristProfile.last_location)
        ).where(TouristProfile.id == profile.id)
    ).one()
    return lat, lon, profile.last_location_accuracy_m


def _maps_link(lat: float, lon: float) -> str:
    return (
        f"https://www.openstreetmap.org/?mlat={lat:.5f}&mlon={lon:.5f}#map=17/{lat:.5f}/{lon:.5f}"
    )


def trigger_sos(
    db: Session,
    user: User,
    profile: TouristProfile,
    location: tuple[float, float, float | None] | None,
    message: str | None,
    now: datetime,
) -> SosResult:
    """The caller commits and publishes the dashboard event."""
    existing = active_sos(db, user.id)
    if existing is not None:
        return SosResult(existing, created=False, contacts_notified=0, lat=None, lon=None)

    if location is None:
        location = _recent_shared_location(db, profile, now)

    incident = Incident(
        reporter_user_id=user.id,
        category_id=None,  # SOS bypasses classification
        description=message or DEFAULT_DESCRIPTION,
        language="en",
        severity=Severity.CRITICAL,  # stays CRITICAL until an operator downgrades it
        status=IncidentStatus.NEW,
        is_sos=True,
    )
    db.add(incident)
    db.flush()

    lat = lon = None
    if location is not None:
        lat, lon, accuracy_m = location
        add_incident_location(db, incident, lat, lon, accuracy_m)
        # Also keep it as the latest location, so staff can follow it during the SOS.
        profile.last_location = WKTElement(f"POINT({lon} {lat})", srid=4326)
        profile.last_location_accuracy_m = accuracy_m
        profile.last_location_at = now
        profile.last_location_expires_at = now + timedelta(days=settings.location_retention_days)

    where = f" Location: {_maps_link(lat, lon)}" if lat is not None else " Location unknown."
    contacts = db.scalars(
        select(EmergencyContact).where(EmergencyContact.tourist_profile_id == profile.id)
    ).all()
    for contact in contacts:
        sandbox_sms.send(
            db,
            recipient=contact.phone,
            kind="sos_contact_alert",
            title=f"SOS from {user.full_name}",
            body=f"{user.full_name} pressed SOS at {now:%H:%M} UTC.{where} "
            "If you cannot reach them, call 112.",
            incident_id=incident.id,
        )
    sandbox_email.send(
        db,
        recipient=user.email,
        user_id=user.id,
        kind="sos_confirmation",
        title=f"Your SOS #{incident.id} was received",
        body=f"Your SOS was received at {now:%H:%M} UTC and is shown to operators. "
        f"{len(contacts)} emergency contact(s) were notified (simulated).",
        incident_id=incident.id,
    )
    notify_in_app(
        db,
        user.id,
        kind="sos_received",
        title=f"SOS #{incident.id} received",
        body="Operators can see your SOS. This prototype only simulates dispatch - "
        "call 112 now if you are in danger. Tourist helpline: 1363.",
        incident_id=incident.id,
    )
    record_event(
        db,
        "sos.triggered",
        actor_user_id=user.id,
        target_type="incident",
        target_id=incident.id,
        details={"with_location": lat is not None, "contacts_notified": len(contacts)},
    )
    db.flush()
    return SosResult(incident, created=True, contacts_notified=len(contacts), lat=lat, lon=lon)


def cancel_sos(db: Session, incident: Incident, user: User) -> None:
    """The tourist says "I'm safe". Marks the SOS resolved. The caller commits."""
    if incident.status in FINISHED:
        raise InvalidTransition("This SOS has already ended")
    incident.status = IncidentStatus.RESOLVED  # special path: allowed from any open status
    release_assignments(db, incident)
    profile = db.scalar(select(TouristProfile).where(TouristProfile.user_id == user.id))
    contacts = db.scalars(
        select(EmergencyContact).where(EmergencyContact.tourist_profile_id == profile.id)
    ).all()
    for contact in contacts:
        sandbox_sms.send(
            db,
            recipient=contact.phone,
            kind="sos_cancelled",
            title=f"SOS from {user.full_name} cancelled",
            body=f"{user.full_name} has cancelled their SOS and reports being safe.",
            incident_id=incident.id,
        )
    record_event(
        db,
        "sos.cancelled_by_tourist",
        actor_user_id=user.id,
        target_type="incident",
        target_id=incident.id,
    )
    after_incident_finished(db, incident)


def after_incident_finished(db: Session, incident: Incident) -> None:
    """When an SOS ends and the tourist's general consent is off, delete the location that
    was stored only because of the emergency."""
    if not incident.is_sos or incident.status not in FINISHED or incident.reporter_user_id is None:
        return
    db.flush()  # make the new status visible to the query below
    if active_sos(db, incident.reporter_user_id) is not None:
        return  # another SOS is still open
    profile = db.scalar(
        select(TouristProfile).where(TouristProfile.user_id == incident.reporter_user_id)
    )
    if profile is not None and not profile.location_consent:
        clear_location(profile)
    db.flush()
