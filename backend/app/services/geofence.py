"""Server-side geofencing.

For each location fix from a tourist (who has given consent):
1. Ignore the fix if its accuracy is worse than settings.geofence_max_accuracy_m.
2. Store it as the tourist's LATEST location (older fixes are overwritten, not kept).
3. Find the risk zones that contain the point (PostGIS ST_Contains) and the zones that are
   merely nearby (ST_DWithin on geography, in metres) - nearby zones never alert.
4. Dwell/debounce, only for HIGH and CRITICAL zones:
   - remember when the tourist entered the zone ("inside_since"); if the previous fix is
     older than settings.geofence_stale_seconds, the dwell clock starts again;
   - alert once they have been inside for settings.geofence_dwell_seconds;
   - never alert again for that zone within settings.geofence_cooldown_seconds, even if they
     step out and back in (stops repeated alerts when walking along a zone's edge).
5. An alert = an in-app notification + an audit row (+ a dashboard event, sent by the route).

`now` is a parameter so tests can simulate time passing.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from geoalchemy2 import WKTElement
from sqlalchemy import and_, func, not_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.notification import Notification, NotificationChannel
from app.models.risk import ALERT_LEVELS, RiskZone
from app.models.tourist import TouristProfile
from app.models.user import User
from app.services.audit import record_event
from app.services.geo import geography_point


@dataclass
class FixResult:
    accepted: bool
    reason: str | None = None
    inside: list[RiskZone] = field(default_factory=list)
    nearby: list[RiskZone] = field(default_factory=list)
    alerts: list[Notification] = field(default_factory=list)


def _point(lat: float, lon: float):
    return func.ST_SetSRID(func.ST_MakePoint(lon, lat), 4326)


def zones_containing(db: Session, lat: float, lon: float) -> list[RiskZone]:
    query = select(RiskZone).where(func.ST_Contains(RiskZone.geom, _point(lat, lon)))
    return list(db.scalars(query.order_by(RiskZone.id)))


def zones_nearby(db: Session, lat: float, lon: float, metres: float) -> list[RiskZone]:
    """Zones within `metres` of the point that do NOT contain it."""
    query = select(RiskZone).where(
        and_(
            func.ST_DWithin(func.geography(RiskZone.geom), geography_point(lat, lon), metres),
            not_(func.ST_Contains(RiskZone.geom, _point(lat, lon))),
        )
    )
    return list(db.scalars(query.order_by(RiskZone.id)))


def _alert(db: Session, user: User, zone: RiskZone) -> Notification:
    notification = Notification(
        user_id=user.id,
        channel=NotificationChannel.IN_APP,
        kind="geofence_alert",
        title=f"Caution: {zone.base_level.value.lower()}-risk area",
        body=(
            f"You are in '{zone.name}', marked {zone.base_level.value} (a relative "
            "decision-support estimate"
            + (", synthetic demo data" if zone.is_synthetic else "")
            + "). Stay alert and keep to busy, well-lit places. "
            "Emergency: 112. Tourist helpline: 1363."
        ),
        payload={"zone_id": zone.id, "level": zone.base_level.value},
        zone_id=zone.id,
        simulated=False,  # in-app notifications are real; only SMS / e-mail are sandboxed
    )
    db.add(notification)
    record_event(
        db,
        "geofence.alert",
        actor_user_id=user.id,
        target_type="risk_zone",
        target_id=zone.id,
        details={"level": zone.base_level.value},  # no coordinates in the audit log
    )
    return notification


def process_fix(
    db: Session,
    user: User,
    profile: TouristProfile,
    lat: float,
    lon: float,
    accuracy_m: float | None,
    now: datetime,
) -> FixResult:
    """Handle one location fix. The caller has checked consent, and commits afterwards."""
    if accuracy_m is None or accuracy_m > settings.geofence_max_accuracy_m:
        return FixResult(
            accepted=False,
            reason=f"Location accuracy must be {settings.geofence_max_accuracy_m:.0f} m or better",
        )

    # If we have not heard from the tourist for a while, we cannot know they stayed inside
    # the zone the whole time, so every dwell clock starts again.
    previous_fix_at = profile.last_location_at
    stale = previous_fix_at is None or now - previous_fix_at > timedelta(
        seconds=settings.geofence_stale_seconds
    )

    profile.last_location = WKTElement(f"POINT({lon} {lat})", srid=4326)
    profile.last_location_accuracy_m = accuracy_m
    profile.last_location_at = now
    profile.last_location_expires_at = now + timedelta(days=settings.location_retention_days)

    inside = zones_containing(db, lat, lon)
    nearby = zones_nearby(db, lat, lon, settings.geofence_near_m)

    dwell = timedelta(seconds=settings.geofence_dwell_seconds)
    cooldown = timedelta(seconds=settings.geofence_cooldown_seconds)
    # Copy the stored state so SQLAlchemy notices the change when we assign it back.
    state = {key: dict(entry) for key, entry in (profile.geofence_state or {}).items()}
    if stale:
        for entry in state.values():
            entry["inside_since"] = None

    alerts = []
    inside_keys = set()
    for zone in inside:
        if zone.base_level not in ALERT_LEVELS:
            continue
        key = str(zone.id)
        inside_keys.add(key)
        entry = state.setdefault(key, {"inside_since": None, "alerted_at": None})
        if entry["inside_since"] is None:
            entry["inside_since"] = now.isoformat()  # just entered

        dwelled_long_enough = now - datetime.fromisoformat(entry["inside_since"]) >= dwell
        last_alert = entry["alerted_at"]
        cooling_down = last_alert is not None and (
            now - datetime.fromisoformat(last_alert) < cooldown
        )
        if dwelled_long_enough and not cooling_down:
            alerts.append(_alert(db, user, zone))
            entry["alerted_at"] = now.isoformat()

    for key, entry in list(state.items()):
        if key not in inside_keys:
            entry["inside_since"] = None  # left the zone (alerted_at kept for the cooldown)
            last_alert = entry["alerted_at"]
            if last_alert is None or now - datetime.fromisoformat(last_alert) >= cooldown:
                del state[key]  # nothing left to remember

    profile.geofence_state = state
    db.flush()
    return FixResult(accepted=True, inside=inside, nearby=nearby, alerts=alerts)


def clear_location(profile: TouristProfile) -> None:
    """Forget the stored location (used when consent is revoked)."""
    profile.last_location = None
    profile.last_location_accuracy_m = None
    profile.last_location_at = None
    profile.last_location_expires_at = None
    profile.geofence_state = {}
