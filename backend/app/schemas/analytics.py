"""Response shape for GET /analytics/summary."""

from datetime import datetime

from pydantic import BaseModel


class DayCount(BaseModel):
    date: str  # YYYY-MM-DD, India time
    count: int


class AnalyticsSummary(BaseModel):
    days: int
    since: datetime
    total: int
    sos: int
    open_now: int
    needs_review: int
    by_status: dict[str, int]
    by_severity: dict[str, int]
    by_category: dict[str, int]
    by_language: dict[str, int]
    per_day: list[DayCount]
    note: str = (
        "Plain counts of incidents in this database. In the prototype these are demo or test "
        "reports, not real data."
    )
