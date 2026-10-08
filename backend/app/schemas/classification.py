"""Request and response shapes for POST /incident/classify."""

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.incident import Severity
from app.schemas.incident import CategoryOut


class ClassifyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=3, max_length=2000)
    language: str = Field(default="en", min_length=2, max_length=10)
    # Optional location: used only for the "inside a high-risk zone" severity rule.
    lat: float | None = Field(default=None, ge=-90, le=90)
    lon: float | None = Field(default=None, ge=-180, le=180)

    @model_validator(mode="after")
    def both_or_neither(self) -> "ClassifyRequest":
        if (self.lat is None) != (self.lon is None):
            raise ValueError("Give both lat and lon, or neither")
        return self


class Alternative(BaseModel):
    code: str
    confidence: float


class ClassifyResponse(BaseModel):
    category: CategoryOut  # includes the suggested department
    confidence: float
    needs_review: bool
    alternatives: list[Alternative]
    severity: Severity
    severity_reasons: list[str]
    model_version: str
    note: str = (
        "Automatic suggestion for decision support, from a model trained on synthetic data. "
        "An operator can always change it."
    )
