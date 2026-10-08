"""Incident classification: the trained text model suggests one of the 9 categories.

- The suggestion comes with a calibrated confidence; below settings.classify_review_threshold
  it is flagged for human review.
- The model was trained on SYNTHETIC English text only. Other languages are always flagged
  for review until the translation step (Phase 8).
- SOS skips classification entirely (see app/services/sos.py).
"""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.ml.text_classifier import get_classifier
from app.models.incident import IncidentCategory


@dataclass
class ClassificationResult:
    category: IncidentCategory
    confidence: float
    needs_review: bool
    alternatives: list[tuple[str, float]]
    model_version: str
    language_supported: bool


def classify_text(db: Session, text: str, language: str = "en") -> ClassificationResult:
    """Raises app.ml.text_classifier.ModelUnavailable if no model has been trained."""
    classifier = get_classifier()
    prediction = classifier.predict(text)
    category = db.scalar(
        select(IncidentCategory).where(IncidentCategory.code == prediction.category_code)
    )
    language_supported = language in classifier.languages
    needs_review = (
        prediction.confidence < settings.classify_review_threshold or not language_supported
    )
    return ClassificationResult(
        category=category,
        confidence=prediction.confidence,
        needs_review=needs_review,
        alternatives=prediction.alternatives,
        model_version=prediction.model_version,
        language_supported=language_supported,
    )
