"""Risk routes.

- GET  /risk-zone?bbox=minLon,minLat,maxLon,maxLat  zones for the map (GeoJSON), with the level
  each zone has right now (fixed for hand-drawn zones, model-based for grid cells)
- POST /risk/predict  staff: run the risk model for a day and store the predictions

Levels are RELATIVE decision-support estimates, never predictions that a crime will occur.
"""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import CurrentUser, DbSession, StaffUser
from app.ml.risk_features import bin_of
from app.ml.risk_model import RiskModelUnavailable
from app.schemas.risk import RiskPredictRequest, RiskPredictResponse
from app.services.audit import record_event
from app.services.risk import predict_day
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


@router.post("/risk/predict", response_model=RiskPredictResponse)
def predict(body: RiskPredictRequest, staff: StaffUser, db: DbSession) -> RiskPredictResponse:
    day = body.date or bin_of(datetime.now(UTC))[0]
    try:
        summary = predict_day(db, day, body.rain_mm, body.temp_max_c)
    except RiskModelUnavailable as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from None
    record_event(
        db,
        "risk.predicted",
        actor_user_id=staff.id,
        details={
            "date": str(day),
            "model_version": summary.model_version,
            "by_level": summary.by_level,
            "weather_source": summary.weather_source,
        },
    )
    db.commit()
    return RiskPredictResponse(
        model_version=summary.model_version,
        date=summary.day,
        time_bins=summary.time_bins,
        cells=summary.cells,
        rows_written=summary.rows_written,
        by_level=summary.by_level,
        weather_source=summary.weather_source,
    )
