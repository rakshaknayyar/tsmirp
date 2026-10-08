"""Risk zones: seeding the SYNTHETIC demo zones, and fetching zones for the map.

The map shows each zone's EFFECTIVE level right now (app/services/risk.py): the fixed level of
a hand-drawn zone, or the risk model's level for a grid cell.
"""

import json
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.risk import RiskLevel, RiskZone
from app.services.geo import geography_point
from app.services.risk import effective_levels


def seed_zones(db: Session, path: Path) -> tuple[int, int]:
    """Create or update zones from a JSON file of circles (centre + radius).

    Each circle is turned into a polygon with PostGIS ST_Buffer on geography, so the radius is
    in real metres. Returns (created, updated). The caller commits.
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    created = updated = 0
    for spec in data["zones"]:
        circle = func.geometry(
            func.ST_Buffer(geography_point(spec["lat"], spec["lon"]), spec["radius_m"])
        )
        zone = db.scalar(select(RiskZone).where(RiskZone.name == spec["name"]))
        if zone is None:
            zone = RiskZone(name=spec["name"])
            db.add(zone)
            created += 1
        else:
            updated += 1
        zone.description = spec.get("description")
        zone.geom = circle
        zone.base_level = RiskLevel(spec["level"])
        zone.is_synthetic = True
        zone.source = data.get("source", "synthetic-seed")
    db.flush()
    return created, updated


def zones_geojson(
    db: Session, min_lon: float, min_lat: float, max_lon: float, max_lat: float
) -> dict:
    """All zones overlapping the box, as a GeoJSON FeatureCollection (for Leaflet)."""
    box = func.ST_MakeEnvelope(min_lon, min_lat, max_lon, max_lat, 4326)
    rows = db.execute(
        select(RiskZone, func.ST_AsGeoJSON(RiskZone.geom))
        .where(func.ST_Intersects(RiskZone.geom, box))
        .order_by(RiskZone.id)
    ).all()
    levels = effective_levels(db, [zone for zone, _ in rows], datetime.now(UTC))
    features = [
        {
            "type": "Feature",
            "geometry": json.loads(geometry),
            "properties": {
                "id": zone.id,
                "name": zone.name,
                "description": zone.description,
                "kind": zone.kind.value,
                "level": levels[zone.id].level.value,
                "level_source": levels[zone.id].source,
                "score": levels[zone.id].score,
                "is_synthetic": zone.is_synthetic,
            },
        }
        for zone, geometry in rows
    ]
    return {
        "type": "FeatureCollection",
        "features": features,
        "note": "Relative risk levels for decision support, not predictions of crime. "
        "Zones marked is_synthetic are demonstration data.",
    }
