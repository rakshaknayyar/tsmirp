"""Request and response shapes for incidents."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.incident import IncidentStatus, Severity


class LocationIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    accuracy_m: float | None = Field(default=None, ge=0, le=100_000)


class LocationOut(BaseModel):
    lat: float
    lon: float
    accuracy_m: float | None
    recorded_at: datetime


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    name: str
    department: str


class IncidentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")  # tourists cannot set severity, status, etc.

    description: str = Field(min_length=5, max_length=2000)
    category_code: str | None = Field(default=None, max_length=30)
    language: str = Field(default="en", min_length=2, max_length=10)
    location: LocationIn | None = None


class IncidentOut(BaseModel):
    id: int
    reporter_user_id: int | None
    category: CategoryOut | None
    description: str
    language: str
    severity: Severity
    status: IncidentStatus
    is_sos: bool
    confidence: float | None
    created_at: datetime
    updated_at: datetime
    # None when there is no location, or when the viewer may not see it (consent rules).
    location: LocationOut | None


class StatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: IncidentStatus
    note: str | None = Field(default=None, max_length=500)
