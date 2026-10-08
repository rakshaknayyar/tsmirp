"""POST /incident/classify - suggest a category, department and severity for a description.

Hindi and romanised Hindi are translated to English first (word list), and the response shows
the English text the model actually read. Does not store anything. Rate-limited per user.
Returns 503 if no model has been trained.
"""

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser, DbSession
from app.core.rate_limit import classify_limiter
from app.ml.text_classifier import ModelUnavailable
from app.schemas.classification import Alternative, ClassifyRequest, ClassifyResponse
from app.schemas.incident import CategoryOut
from app.services.classification import classify_text
from app.services.incidents import in_high_risk_zone
from app.services.language import prepare_text
from app.services.severity import assess_severity

router = APIRouter(tags=["classification"])


@router.post("/incident/classify", response_model=ClassifyResponse)
def classify(body: ClassifyRequest, user: CurrentUser, db: DbSession) -> ClassifyResponse:
    classify_limiter.check(f"user:{user.id}")
    prepared = prepare_text(body.text, body.language)
    try:
        result = classify_text(db, prepared)
    except ModelUnavailable as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from None

    high_zone = body.lat is not None and in_high_risk_zone(db, body.lat, body.lon)
    severity = assess_severity(
        prepared.text_for_rules, result.category.code, in_high_risk_zone=high_zone
    )
    note = ClassifyResponse.model_fields["note"].default
    translation = prepared.translation
    if translation is not None:
        note += (
            f" The text was translated word by word from '{prepared.language}' with a simple "
            "word list, so please check it."
        )
    return ClassifyResponse(
        category=CategoryOut.model_validate(result.category),
        confidence=result.confidence,
        needs_review=result.needs_review,
        alternatives=[Alternative(code=c, confidence=p) for c, p in result.alternatives],
        severity=severity.severity,
        severity_reasons=severity.reasons,
        model_version=result.model_version,
        language=prepared.language,
        language_detected=prepared.language_detected,
        english_text=prepared.english,
        translation_method=translation.method if translation else None,
        unknown_words=translation.unknown_words if translation else [],
        note=note,
    )
