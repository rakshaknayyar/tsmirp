"""SOS routes (tourists only).

- POST /sos               trigger an SOS (rate-limited; returns the open SOS if there is one)
- POST /sos/{id}/cancel   "I'm safe" - ends the tourist's own SOS
"""

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy import select

from app.api.deps import DbSession, TouristUser
from app.core.rate_limit import sos_limiter
from app.models.incident import Incident
from app.models.resource import ResourceType
from app.models.tourist import TouristProfile
from app.schemas.sos import SosRequest, SosResponse
from app.services.events import event_bus
from app.services.incidents import InvalidTransition, to_incident_out
from app.services.resources import nearest_resources
from app.services.sos import cancel_sos, trigger_sos

router = APIRouter(prefix="/sos", tags=["sos"])


def _publish(db, event_type: str, incident: Incident) -> None:
    payload = to_incident_out(db, incident, viewer=None).model_dump(mode="json")
    event_bus.publish({"type": event_type, "incident": payload})


@router.post("", response_model=SosResponse)
def sos(body: SosRequest, user: TouristUser, db: DbSession, response: Response) -> SosResponse:
    try:
        sos_limiter.check(f"user:{user.id}")
    except HTTPException as exc:
        exc.detail = "Too many SOS requests from this account. Call 112 now if you need help."
        raise
    profile = db.scalar(select(TouristProfile).where(TouristProfile.user_id == user.id))
    location = (
        (body.location.lat, body.location.lon, body.location.accuracy_m) if body.location else None
    )
    result = trigger_sos(db, user, profile, location, body.message, datetime.now(UTC))
    db.commit()

    if result.created:
        response.status_code = status.HTTP_201_CREATED
        _publish(db, "incident.created", result.incident)

    help_nearby = []
    if result.lat is not None:
        for resource_type in (ResourceType.POLICE_STATION, ResourceType.HOSPITAL):
            help_nearby += nearest_resources(db, result.lat, result.lon, [resource_type], 2)
    return SosResponse(
        incident=to_incident_out(db, result.incident, viewer=user),
        created=result.created,
        contacts_notified=result.contacts_notified,
        nearest_help=[
            {
                "id": n.resource.id,
                "name": n.resource.name,
                "resource_type": n.resource.resource_type,
                "source": n.resource.source,
                "capabilities": n.resource.capabilities,
                "availability_sim": n.resource.availability_sim,
                "lat": n.lat,
                "lon": n.lon,
                "distance_m": n.distance_m,
            }
            for n in help_nearby
        ],
    )


@router.post("/{incident_id}/cancel", response_model=SosResponse)
def cancel(incident_id: int, user: TouristUser, db: DbSession) -> SosResponse:
    incident = db.get(Incident, incident_id, with_for_update=True)
    # Only your own SOS; anything else looks like "not found".
    if incident is None or not incident.is_sos or incident.reporter_user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "SOS not found")
    try:
        cancel_sos(db, incident, user)
    except InvalidTransition as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from None
    db.commit()

    _publish(db, "incident.status_changed", incident)
    return SosResponse(
        incident=to_incident_out(db, incident, viewer=user),
        created=False,
        contacts_notified=0,
        nearest_help=[],
        advice="SOS cancelled. Call 112 if you need help again.",
    )
