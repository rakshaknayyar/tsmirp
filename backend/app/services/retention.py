"""Retention job: permanently delete locations whose expiry time has passed.

Every stored location gets an expiry time when it is saved (settings.location_retention_days,
30 days by default). Expired locations are already hidden by the API; this job removes them
from the database for good:
- incident locations (incident_locations rows) whose expires_at has passed;
- a tourist's latest location (tourist_profiles.last_location) once it has expired.
Incidents themselves are kept (without location) for the record.

Run it daily, e.g. with Windows Task Scheduler or cron:  python -m app.cli purge-expired
"""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.incident import IncidentLocation
from app.models.tourist import TouristProfile
from app.services.audit import record_event
from app.services.geofence import clear_location


@dataclass(frozen=True)
class PurgeResult:
    incident_locations_deleted: int
    tourist_locations_cleared: int


def purge_expired(db: Session, now: datetime) -> PurgeResult:
    """Delete everything that expired before `now`, audit it, and leave the commit to the
    caller. `now` is a parameter so tests can pretend time has passed."""
    deleted = db.execute(
        delete(IncidentLocation).where(IncidentLocation.expires_at <= now)
    ).rowcount
    profiles = db.scalars(
        select(TouristProfile).where(
            TouristProfile.last_location.is_not(None),
            TouristProfile.last_location_expires_at <= now,
        )
    ).all()
    for profile in profiles:
        clear_location(profile)
    db.flush()
    result = PurgeResult(deleted, len(profiles))
    record_event(
        db,
        "retention.purged",
        details={
            "incident_locations_deleted": result.incident_locations_deleted,
            "tourist_locations_cleared": result.tourist_locations_cleared,
        },
    )
    return result
