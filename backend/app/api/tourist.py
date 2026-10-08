"""Tourist-only routes: own profile, location consent, own emergency contacts.

Object-level authorisation: every query is filtered by the logged-in tourist's own profile,
so one tourist can never read or delete another tourist's data (they just get 404).
"""

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import DbSession, TouristUser
from app.models.tourist import EmergencyContact, TouristProfile
from app.models.user import User
from app.schemas.tourist import (
    ConsentUpdate,
    EmergencyContactCreate,
    EmergencyContactOut,
    ProfileOut,
    ProfileUpdate,
)
from app.services.audit import record_event

router = APIRouter(prefix="/tourist", tags=["tourist"])


def _own_profile(user: User, db: Session) -> TouristProfile:
    profile = db.scalar(select(TouristProfile).where(TouristProfile.user_id == user.id))
    if profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tourist profile not found")
    return profile


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
    """Grant or revoke location consent. Every change is recorded in the audit log."""
    profile = _own_profile(user, db)
    if body.location_consent != profile.location_consent:
        profile.location_consent = body.location_consent
        profile.consent_time = datetime.now(UTC)
        action = "consent.location_granted" if body.location_consent else "consent.location_revoked"
        record_event(
            db, action, actor_user_id=user.id, target_type="tourist_profile", target_id=profile.id
        )
        db.commit()
    return profile


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
