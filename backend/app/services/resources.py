"""Finding, ranking and (SIMULATED) assigning of response resources.

Nearest search: PostGIS K-nearest-neighbour operator <-> on the geography column, which uses
the GiST index instead of measuring the distance to every resource.

Recommendation ranking for an incident (a simple, explainable rule; an assumption of the
prototype, not a validated dispatch policy):
  1. only resource types that suit the category's department (e.g. Police -> police_station)
  2. only within settings.recommend_max_distance_m (PostGIS ST_DWithin)
  3. OFFLINE resources are left out
  4. AVAILABLE before BUSY
  5. resources with the preferred capability first (e.g. hospital with emergency department)
  6. then nearer first (straight-line distance)
"""

from collections.abc import Collection
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.incident import Incident, IncidentCategory, IncidentStatus
from app.models.resource import (
    AssignmentStatus,
    Availability,
    ResourceType,
    ResponseAssignment,
    ResponseResource,
)
from app.models.user import User
from app.services.geo import geography_point
from app.services.incidents import change_status

DEPARTMENT_RESOURCE_TYPES: dict[str, tuple[ResourceType, ...]] = {
    "Police": (ResourceType.POLICE_STATION,),
    "Medical": (ResourceType.HOSPITAL,),
    "Fire": (ResourceType.FIRE_STATION,),
    "Disaster Management": (ResourceType.FIRE_STATION, ResourceType.POLICE_STATION),
    "Tourist Helpdesk": (ResourceType.POLICE_STATION,),
}
CATEGORY_PREFERRED_CAPABILITY = {"medical_emergency": "emergency", "accident": "emergency"}
AVAILABILITY_ORDER = {Availability.AVAILABLE: 0, Availability.BUSY: 1}
CANDIDATE_POOL = 20  # nearest candidates considered before re-ranking


class ResourceUnavailable(Exception):
    pass


@dataclass
class NearbyResource:
    resource: ResponseResource
    distance_m: float  # straight-line, metres
    lat: float
    lon: float
    capability_match: bool = False


def nearest_resources(
    db: Session,
    lat: float,
    lon: float,
    types: Collection[ResourceType] | None,
    k: int,
    *,
    exclude_offline: bool = False,
    max_distance_m: float | None = None,
) -> list[NearbyResource]:
    point = geography_point(lat, lon)
    query = select(
        ResponseResource,
        func.ST_Distance(ResponseResource.geog, point),  # metres on the WGS84 ellipsoid
        func.ST_Y(func.geometry(ResponseResource.geog)),  # latitude
        func.ST_X(func.geometry(ResponseResource.geog)),  # longitude
    )
    if types:
        query = query.where(ResponseResource.resource_type.in_(list(types)))
    if exclude_offline:
        query = query.where(ResponseResource.availability_sim != Availability.OFFLINE)
    if max_distance_m is not None:
        # ST_DWithin on geography: "within this many metres", and it can use the GiST index.
        query = query.where(func.ST_DWithin(ResponseResource.geog, point, max_distance_m))
    query = query.order_by(ResponseResource.geog.op("<->")(point)).limit(k)
    return [
        NearbyResource(resource=r, distance_m=d, lat=y, lon=x) for r, d, y, x in db.execute(query)
    ]


def recommend_resources(
    db: Session, incident: Incident, lat: float, lon: float, k: int
) -> list[NearbyResource]:
    category = db.get(IncidentCategory, incident.category_id) if incident.category_id else None
    types = DEPARTMENT_RESOURCE_TYPES.get(category.department) if category else None
    wanted = CATEGORY_PREFERRED_CAPABILITY.get(category.code) if category else None

    candidates = nearest_resources(
        db,
        lat,
        lon,
        types,
        CANDIDATE_POOL,
        exclude_offline=True,
        max_distance_m=settings.recommend_max_distance_m,
    )
    for candidate in candidates:
        candidate.capability_match = (
            wanted is not None and wanted in candidate.resource.capabilities
        )
    candidates.sort(
        key=lambda c: (
            AVAILABILITY_ORDER[c.resource.availability_sim],
            not c.capability_match,
            c.distance_m,
        )
    )
    return candidates[:k]


def assign_resource(
    db: Session,
    incident: Incident,
    resource: ResponseResource,
    staff: User,
    distance_m: float | None,
    note: str | None,
) -> ResponseAssignment:
    """SIMULATED dispatch: record the assignment, mark the resource BUSY, move the incident
    to ASSIGNED. Nothing is sent to any real service. The caller audits and commits."""
    if resource.availability_sim != Availability.AVAILABLE:
        raise ResourceUnavailable(f"{resource.name} is {resource.availability_sim}")
    change_status(incident, IncidentStatus.ASSIGNED, by_assignment=True)  # may raise
    resource.availability_sim = Availability.BUSY
    assignment = ResponseAssignment(
        incident_id=incident.id,
        resource_id=resource.id,
        assigned_by_user_id=staff.id,
        distance_m=distance_m,
        status=AssignmentStatus.ACTIVE,
        note=note,
    )
    db.add(assignment)
    db.flush()
    return assignment


def release_assignments(db: Session, incident: Incident) -> list[ResponseAssignment]:
    """When an incident is resolved or closed, free its resources (simulated)."""
    active = db.scalars(
        select(ResponseAssignment).where(
            ResponseAssignment.incident_id == incident.id,
            ResponseAssignment.status == AssignmentStatus.ACTIVE,
        )
    ).all()
    for assignment in active:
        assignment.status = AssignmentStatus.RELEASED
        assignment.released_at = datetime.now(UTC)
        resource = db.get(ResponseResource, assignment.resource_id)
        if resource is not None and resource.availability_sim == Availability.BUSY:
            resource.availability_sim = Availability.AVAILABLE
    db.flush()
    return list(active)


def distance_to_resource_m(
    db: Session, resource: ResponseResource, lat: float, lon: float
) -> float:
    return db.scalar(
        select(func.ST_Distance(ResponseResource.geog, geography_point(lat, lon))).where(
            ResponseResource.id == resource.id
        )
    )
