"""Request and response shapes for response resources and (simulated) assignments."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.resource import AssignmentStatus, Availability, ResourceType
from app.schemas.incident import IncidentOut


class NearbyResourceOut(BaseModel):
    id: int
    name: str
    resource_type: ResourceType
    source: str
    capabilities: list[str]
    availability_sim: Availability  # SIMULATED, not live
    lat: float
    lon: float
    distance_m: float
    # Always "straight_line": real road distance is longer.
    distance_kind: Literal["straight_line"] = "straight_line"


class RecommendedResourceOut(NearbyResourceOut):
    capability_match: bool


class AssignRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    resource_id: int
    note: str | None = Field(default=None, max_length=500)


class AssignmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    incident_id: int
    resource_id: int
    assigned_at: datetime
    distance_m: float | None
    status: AssignmentStatus
    simulated: Literal[True] = True  # no real unit is ever contacted


class AssignResult(BaseModel):
    incident: IncidentOut
    assignment: AssignmentOut
