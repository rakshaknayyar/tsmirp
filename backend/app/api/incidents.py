"""Incident routes.

- Tourists report incidents and see only their own (others' incidents give 404).
- Staff (operator, supervisor, administrator) see all incidents and change their status.
- Every create / status change is audited and pushed live to the dashboard.
"""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, DbSession, StaffUser, TouristUser
from app.models.incident import Incident, IncidentCategory, IncidentStatus
from app.models.tourist import TouristProfile
from app.models.user import STAFF_ROLES, User
from app.schemas.incident import CategoryOut, IncidentCreate, IncidentOut, StatusUpdate
from app.services.audit import record_event
from app.services.events import event_bus
from app.services.incidents import (
    InvalidTransition,
    UnknownCategory,
    change_status,
    create_incident,
    to_incident_out,
)
from app.services.resources import release_assignments

router = APIRouter(tags=["incidents"])


def _visible_incident(db: Session, incident_id: int, user: User) -> Incident:
    """Load an incident the user is allowed to see, or 404 (also for other tourists' ones)."""
    incident = db.get(Incident, incident_id)
    if incident is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Incident not found")
    if user.role not in STAFF_ROLES and incident.reporter_user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Incident not found")
    return incident


def _broadcast(db: Session, event_type: str, incident: Incident) -> None:
    out = to_incident_out(db, incident, viewer=None)
    event_bus.publish({"type": event_type, "incident": out.model_dump(mode="json")})


@router.get("/incident-categories", response_model=list[CategoryOut])
def list_categories(user: CurrentUser, db: DbSession) -> list[IncidentCategory]:
    return list(db.scalars(select(IncidentCategory).order_by(IncidentCategory.id)))


@router.post("/incidents", response_model=IncidentOut, status_code=status.HTTP_201_CREATED)
def report_incident(body: IncidentCreate, user: TouristUser, db: DbSession) -> IncidentOut:
    if body.location is not None:
        consent = db.scalar(
            select(TouristProfile.location_consent).where(TouristProfile.user_id == user.id)
        )
        if not consent:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "Location can only be attached after you turn on location consent "
                "(PUT /tourist/consent). You can also report without a location.",
            )
    try:
        incident = create_incident(db, reporter=user, body=body)
    except UnknownCategory:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "Unknown incident category"
        ) from None
    record_event(
        db,
        "incident.reported",
        actor_user_id=user.id,
        target_type="incident",
        target_id=incident.id,
        details={"with_location": body.location is not None},
    )
    db.commit()

    _broadcast(db, "incident.created", incident)  # only after the commit succeeded
    return to_incident_out(db, incident, viewer=user)


@router.get("/incidents", response_model=list[IncidentOut])
def list_incidents(
    user: CurrentUser,
    db: DbSession,
    status_filter: Annotated[IncidentStatus | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[IncidentOut]:
    query = select(Incident)
    if user.role not in STAFF_ROLES:
        query = query.where(Incident.reporter_user_id == user.id)  # tourists: own only
    if status_filter is not None:
        query = query.where(Incident.status == status_filter)
    query = query.order_by(Incident.created_at.desc(), Incident.id.desc())
    incidents = db.scalars(query.limit(limit).offset(offset))
    return [to_incident_out(db, incident, viewer=user) for incident in incidents]


@router.get("/incidents/{incident_id}", response_model=IncidentOut)
def get_incident(incident_id: int, user: CurrentUser, db: DbSession) -> IncidentOut:
    return to_incident_out(db, _visible_incident(db, incident_id, user), viewer=user)


@router.patch("/incidents/{incident_id}/status", response_model=IncidentOut)
def update_status(
    incident_id: int, body: StatusUpdate, staff: StaffUser, db: DbSession
) -> IncidentOut:
    # FOR UPDATE locks the row, so two operators changing it at once cannot clash.
    incident = db.get(Incident, incident_id, with_for_update=True)
    if incident is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Incident not found")
    try:
        old_status = change_status(incident, body.status)
    except InvalidTransition as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from None
    if body.status in (IncidentStatus.RESOLVED, IncidentStatus.CLOSED):
        release_assignments(db, incident)  # simulated resources become AVAILABLE again
    record_event(
        db,
        "incident.status_changed",
        actor_user_id=staff.id,
        target_type="incident",
        target_id=incident.id,
        details={"from": old_status.value, "to": body.status.value, "note": body.note},
    )
    db.commit()

    _broadcast(db, "incident.status_changed", incident)
    return to_incident_out(db, incident, viewer=staff)
