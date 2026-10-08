"""POST /incident/classify - suggest a category, department and severity for a description.

Does not store anything. Rate-limited per user. Returns 503 if no model has been trained.
"""

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser, DbSession
from app.core.rate_limit import classify_limiter
from app.ml.text_classifier import ModelUnavailable
from app.schemas.classification import Alternative, ClassifyRequest, ClassifyResponse
from app.schemas.incident import CategoryOut
from app.services.classification import classify_text
from app.services.incidents import in_high_risk_zone
from app.services.severity import assess_severity

router = APIRouter(tags=["classification"])


@router.post("/incident/classify", response_model=ClassifyResponse)
def classify(body: ClassifyRequest, user: CurrentUser, db: DbSession) -> ClassifyResponse:
    classify_limiter.check(f"user:{user.id}")
    try:
        result = classify_text(db, body.text, body.language)
    except ModelUnavailable as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from None

    high_zone = body.lat is not None and in_high_risk_zone(db, body.lat, body.lon)
    severity = assess_severity(body.text, result.category.code, in_high_risk_zone=high_zone)
    note = ClassifyResponse.model_fields["note"].default
    if not result.language_supported:
        note += f" Language '{body.language}' is not supported yet, so this needs review."
    return ClassifyResponse(
        category=CategoryOut.model_validate(result.category),
        confidence=result.confidence,
        needs_review=result.needs_review,
        alternatives=[Alternative(code=c, confidence=p) for c, p in result.alternatives],
        severity=severity.severity,
        severity_reasons=severity.reasons,
        model_version=result.model_version,
        note=note,
    )
