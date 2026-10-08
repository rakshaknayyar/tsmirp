"""GET /analytics/summary?days=7 - incident counts for the dashboard (staff only)."""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import DbSession, StaffUser
from app.schemas.analytics import AnalyticsSummary
from app.services.analytics import summary

router = APIRouter(tags=["analytics"])


@router.get("/analytics/summary", response_model=AnalyticsSummary)
def analytics_summary(
    staff: StaffUser,
    db: DbSession,
    days: Annotated[int, Query(ge=1, le=90)] = 7,
) -> dict:
    return summary(db, days, datetime.now(UTC))
