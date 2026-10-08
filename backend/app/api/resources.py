"""Resource routes: nearby search, recommendations for an incident, SIMULATED assignment.

All distances are straight-line approximations (see app/services/geo.py).
"""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import CurrentUser, DbSession, StaffUser
from app.models.incident import Incident
from app.models.resource import ResourceType, ResponseResource
from app.schemas.resource import (
    AssignmentOut,
    AssignRequest,
    AssignResult,
    NearbyResourceOut,
    RecommendedResourceOut,
)
from app.services.audit import record_event
from app.services.events import event_bus
from app.services.incidents import InvalidTransition, to_incident_out
from app.services.resources import (
    NearbyResource,
    ResourceUnavailable,
    assign_resource,
    distance_to_resource_m,
    nearest_resources,
    recommend_resources,
)

router = APIRouter(tags=["resources"])


def _to_out(item: NearbyResource) -> dict:
    r = item.resource
    return {
        "id": r.id,
        "name": r.name,
        "resource_type": r.resource_type,
        "source": r.source,
        "capabilities": r.capabilities,
        "availability_sim": r.availability_sim,
        "lat": item.lat,
        "lon": item.lon,
        "distance_m": item.distance_m,
        "capability_match": item.capability_match,
    }


@router.get("/nearby-resources", response_model=list[NearbyResourceOut])
def nearby_resources(
    user: CurrentUser,
    db: DbSession,
    lat: Annotated[float, Query(ge=-90, le=90)],
    lon: Annotated[float, Query(ge=-180, le=180)],
    resource_type: Annotated[ResourceType | None, Query(alias="type")] = None,
    k: Annotated[int, Query(ge=1, le=50)] = 5,
) -> list[dict]:
    types = [resource_type] if resource_type else None
    return [_to_out(item) for item in nearest_resources(db, lat, lon, types, k)]


@router.get(
    "/incidents/{incident_id}/recommended-resources",
    response_model=list[RecommendedResourceOut],
)
def recommended_resources(
    incident_id: int,
    staff: StaffUser,
    db: DbSession,
    k: Annotated[int, Query(ge=1, le=20)] = 3,
) -> list[dict]:
    incident = db.get(Incident, incident_id)
    if incident is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Incident not found")
    # Uses the location only if this staff member may see it (consent / SOS rules).
    location = to_incident_out(db, incident, viewer=staff).location
    if location is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "This incident has no location that you may see"
        )
    ranked = recommend_resources(db, incident, location.lat, location.lon, k)
    return [_to_out(item) for item in ranked]


@router.post("/incidents/{incident_id}/assign", response_model=AssignResult)
def assign(incident_id: int, body: AssignRequest, staff: StaffUser, db: DbSession) -> AssignResult:
    """SIMULATED dispatch: records the decision only; no real unit is contacted."""
    # Lock both rows so two operators cannot assign the same incident/resource at once.
    incident = db.get(Incident, incident_id, with_for_update=True)
    if incident is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Incident not found")
    resource = db.get(ResponseResource, body.resource_id, with_for_update=True)
    if resource is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Resource not found")

    location = to_incident_out(db, incident, viewer=staff).location
    distance_m = (
        distance_to_resource_m(db, resource, location.lat, location.lon) if location else None
    )
    try:
        assignment = assign_resource(db, incident, resource, staff, distance_m, body.note)
    except (InvalidTransition, ResourceUnavailable) as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from None
    record_event(
        db,
        "incident.assigned",
        actor_user_id=staff.id,
        target_type="incident",
        target_id=incident.id,
        details={"resource_id": resource.id, "simulated": True},
    )
    db.commit()

    out = to_incident_out(db, incident, viewer=staff)
    event_bus.publish(
        {
            "type": "incident.status_changed",
            "incident": to_incident_out(db, incident, viewer=None).model_dump(mode="json"),
        }
    )
    return AssignResult(incident=out, assignment=AssignmentOut.model_validate(assignment))
