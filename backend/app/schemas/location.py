"""Shapes for location fixes, geofence results, zones and notifications."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.notification import NotificationChannel
from app.models.risk import RiskLevel


class LocationFix(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    # GPS accuracy radius in metres. Fixes without it, or too inaccurate, are ignored.
    accuracy_m: float | None = Field(default=None, ge=0, le=100_000)


class ZoneBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    level: RiskLevel
    is_synthetic: bool


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: str
    channel: NotificationChannel
    title: str
    body: str
    incident_id: int | None
    zone_id: int | None
    simulated: bool
    created_at: datetime
    read_at: datetime | None


class FixResultOut(BaseModel):
    accepted: bool
    reason: str | None
    inside_zones: list[ZoneBrief]
    nearby_zones: list[ZoneBrief]
    alerts: list[NotificationOut]


class TouristLocationOut(BaseModel):
    user_id: int
    lat: float
    lon: float
    accuracy_m: float | None
    recorded_at: datetime
    # Why the operator may see it: the tourist's consent, or an active SOS.
    basis: Literal["consent", "active_sos"]
