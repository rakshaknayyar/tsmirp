"""Request and response shapes for SOS."""

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.incident import IncidentOut, LocationIn
from app.schemas.resource import NearbyResourceOut


class SosRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    location: LocationIn | None = None
    message: str | None = Field(default=None, max_length=500)


class SosResponse(BaseModel):
    incident: IncidentOut
    created: bool  # False = you already had an open SOS; this is that one
    contacts_notified: int  # sandbox SMS only - nothing is really sent
    nearest_help: list[NearbyResourceOut]  # straight-line distances
    advice: str = "This prototype only simulates dispatch. Call 112 now if you are in danger."
