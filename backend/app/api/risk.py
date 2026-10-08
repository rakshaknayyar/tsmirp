"""GET /risk-zone?bbox=minLon,minLat,maxLon,maxLat - risk zones for the map, as GeoJSON.

Levels are RELATIVE decision-support estimates, never predictions that a crime will occur.
"""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import CurrentUser, DbSession
from app.services.zones import zones_geojson

router = APIRouter(tags=["risk"])


def _parse_bbox(bbox: str) -> tuple[float, float, float, float]:
    try:
        min_lon, min_lat, max_lon, max_lat = (float(part) for part in bbox.split(","))
    except ValueError:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "bbox must be minLon,minLat,maxLon,maxLat"
        ) from None
    valid = (
        -180 <= min_lon < max_lon <= 180
        and -90 <= min_lat < max_lat <= 90
        and (max_lon - min_lon) * (max_lat - min_lat) <= 25  # at most ~5 x 5 degrees
    )
    if not valid:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "bbox out of range or too large")
    return min_lon, min_lat, max_lon, max_lat


@router.get("/risk-zone")
def risk_zones(
    user: CurrentUser,
    db: DbSession,
    bbox: Annotated[str, Query(description="minLon,minLat,maxLon,maxLat")],
) -> dict:
    return zones_geojson(db, *_parse_bbox(bbox))
