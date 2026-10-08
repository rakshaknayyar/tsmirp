"""Analytics for the dashboard: simple counts of incidents, computed by the database.

Everything is a plain count (no estimates), so the numbers can be checked by hand with SQL.
In this prototype the incidents are demo or test data, not real reports.
"""

from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.ml.risk_features import IST
from app.models.incident import Incident, IncidentCategory, IncidentStatus

OPEN_STATUSES = [
    IncidentStatus.NEW,
    IncidentStatus.ACKNOWLEDGED,
    IncidentStatus.ASSIGNED,
    IncidentStatus.EN_ROUTE,
]


def _counts(db: Session, column, since: datetime, *joins) -> dict[str, int]:
    query = select(column, func.count()).select_from(Incident)
    for target, condition in joins:
        query = query.outerjoin(target, condition)
    rows = db.execute(query.where(Incident.created_at >= since).group_by(column)).all()
    return {str(key) if key is not None else "uncategorised": n for key, n in rows}


def summary(db: Session, days: int, now: datetime) -> dict:
    """Counts for incidents created in the last `days` days (India time, today included)."""
    first_day: date = now.astimezone(IST).date() - timedelta(days=days - 1)
    since = datetime(first_day.year, first_day.month, first_day.day, tzinfo=IST)
    in_period = Incident.created_at >= since

    total = db.scalar(select(func.count()).select_from(Incident).where(in_period))
    sos = db.scalar(select(func.count()).where(in_period, Incident.is_sos.is_(True)))
    open_now = db.scalar(select(func.count()).where(Incident.status.in_(OPEN_STATUSES)))
    # Same rule as app/services/incidents.needs_review: no category, or low confidence.
    needs_review = db.scalar(
        select(func.count()).where(
            in_period,
            Incident.is_sos.is_(False),
            (Incident.category_id.is_(None))
            | (Incident.confidence < settings.classify_review_threshold),
        )
    )
    local_day = func.date(func.timezone("Asia/Kolkata", Incident.created_at))
    per_day_rows = dict(
        db.execute(select(local_day, func.count()).where(in_period).group_by(local_day)).all()
    )
    per_day = [
        {"date": str(d), "count": per_day_rows.get(d, 0)}
        for d in (first_day + timedelta(days=i) for i in range(days))
    ]
    return {
        "days": days,
        "since": since,
        "total": total,
        "sos": sos,
        "open_now": open_now,  # all open incidents, whatever their date
        "needs_review": needs_review,
        "by_status": _counts(db, Incident.status, since),
        "by_severity": _counts(db, Incident.severity, since),
        "by_category": _counts(
            db,
            IncidentCategory.code,
            since,
            (IncidentCategory, Incident.category_id == IncidentCategory.id),
        ),
        "by_language": _counts(db, Incident.language, since),
        "per_day": per_day,
    }
