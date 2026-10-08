"""Request and response shapes for POST /incident/classify."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.incident import Severity
from app.schemas.incident import CategoryOut

Language = Literal["en", "hi", "hi-Latn"]


class ClassifyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=3, max_length=2000)
    # Leave empty to detect it automatically from the text.
    language: Language | None = None
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
    language: Language
    language_detected: bool  # True = detected automatically, False = given by the client
    english_text: str  # what the classifier actually read (the translation, if any)
    translation_method: str | None  # None for English
    unknown_words: list[str]  # words the translator did not know
    note: str = (
        "Automatic suggestion for decision support, from a model trained on synthetic data. "
        "An operator can always change it."
    )
