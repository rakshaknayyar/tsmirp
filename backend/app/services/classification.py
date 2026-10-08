"""Incident classification: the trained text model suggests one of the 9 categories.

- The model was trained on SYNTHETIC English text only. Hindi and romanised Hindi are first
  translated to English (app/services/language.py), then classified ("translate, then
  classify").
- The suggestion comes with a calibrated confidence; below settings.classify_review_threshold
  it is flagged for human review.
- If the translation contains no English words at all, the model has nothing real to go on,
  so the confidence is set to 0 and the report always goes to human review.
- SOS skips classification entirely (see app/services/sos.py).
"""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.ml.text_classifier import get_classifier
from app.models.incident import IncidentCategory
from app.services.language import PreparedText


@dataclass
class ClassificationResult:
    category: IncidentCategory
    confidence: float
    needs_review: bool
    alternatives: list[tuple[str, float]]
    model_version: str


def classify_text(db: Session, prepared: PreparedText) -> ClassificationResult:
    """Raises app.ml.text_classifier.ModelUnavailable if no model has been trained."""
    prediction = get_classifier().predict(prepared.english)
    category = db.scalar(
        select(IncidentCategory).where(IncidentCategory.code == prediction.category_code)
    )
    confidence = 0.0 if prepared.understood_nothing else prediction.confidence
    return ClassificationResult(
        category=category,
        confidence=confidence,
        needs_review=confidence < settings.classify_review_threshold,
        alternatives=prediction.alternatives,
        model_version=prediction.model_version,
    )
