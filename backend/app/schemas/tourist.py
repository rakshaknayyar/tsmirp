"""Request and response shapes for the tourist profile, consent and emergency contacts."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

PHONE_PATTERN = r"^\+?[0-9 ]{7,20}$"  # digits and spaces, optional leading +


class ProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    nationality: str | None
    phone: str | None
    preferred_language: str
    location_consent: bool
    consent_time: datetime | None


class ProfileUpdate(BaseModel):
    # Consent is NOT editable here (extra fields are rejected); it has its own audited endpoint.
    model_config = ConfigDict(extra="forbid")

    nationality: str | None = Field(default=None, max_length=60)
    phone: str | None = Field(default=None, pattern=PHONE_PATTERN)
    preferred_language: str = Field(default="en", min_length=2, max_length=10)


class ConsentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    location_consent: bool


class EmergencyContactCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    phone: str = Field(pattern=PHONE_PATTERN)
    relation: str | None = Field(default=None, max_length=40)


class EmergencyContactOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    phone: str
    relation: str | None
