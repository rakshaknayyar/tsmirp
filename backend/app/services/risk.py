"""Risk levels in the app.

- predict_day(): runs the trained risk model for every grid cell and all four 6-hour bins of a
  day, and stores the scores and levels in risk_predictions (with the model_version).
- effective_levels(): the level a zone has RIGHT NOW. Hand-drawn "area" zones keep their fixed
  level; "grid" cells take the latest prediction for the current bin, or LOW if none exists.
  Geofence alerts, the severity rule "inside a high-risk zone" and the map all use this.

Levels are RELATIVE decision-support estimates from a model trained on SYNTHETIC data, never
predictions that a crime will occur.
"""

from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, timedelta

import numpy as np
from geoalchemy2 import WKTElement
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.ml.risk_features import (
    BIN_HOURS,
    TIME_BINS,
    Cell,
    bin_of,
    bin_start,
    fallback_weather,
    feature_matrix,
    grid_cells,
    level_name,
    static_features,
)
from app.ml.risk_model import get_risk_model
from app.models.risk import RiskLevel, RiskPrediction, RiskZone, ZoneKind


@dataclass
class EffectiveLevel:
    level: RiskLevel
    source: str  # human-readable: where the level comes from
    score: float | None = None


@dataclass
class PredictionSummary:
    model_version: str
    day: date
    time_bins: list[datetime]
    cells: int
    rows_written: int
    by_level: dict[str, int]
    weather_source: str


def level_from_score(score: float) -> RiskLevel:
    return RiskLevel(level_name(score, settings.risk_level_thresholds))


def _polygon(cell: Cell) -> WKTElement:
    s, w, n, e = cell.south, cell.west, cell.north, cell.east
    return WKTElement(f"POLYGON(({w} {s}, {e} {s}, {e} {n}, {w} {n}, {w} {s}))", srid=4326)


def ensure_grid_zones(db: Session, cell_size_m: int) -> list[tuple[Cell, RiskZone]]:
    """Create the grid-cell zones the first time; reuse them afterwards."""
    cells = grid_cells(cell_size_m)
    names = [cell.name(cell_size_m) for cell in cells]
    existing = {z.name: z for z in db.scalars(select(RiskZone).where(RiskZone.name.in_(names)))}
    for cell, name in zip(cells, names, strict=True):
        if name not in existing:
            zone = RiskZone(
                name=name,
                kind=ZoneKind.GRID,
                geom=_polygon(cell),
                base_level=RiskLevel.LOW,
                is_synthetic=True,
                source=f"grid-{cell_size_m}m",
                description="Grid cell; its level comes from the risk model (synthetic data).",
            )
            db.add(zone)
            existing[name] = zone
    db.flush()
    return [(cell, existing[name]) for cell, name in zip(cells, names, strict=True)]


def predict_day(
    db: Session, day: date, rain_mm: float | None = None, temp_max_c: float | None = None
) -> PredictionSummary:
    """Score every grid cell for the 4 bins of `day`. Raises RiskModelUnavailable.
    Weather not given is taken from the approximate monthly fallback table."""
    model = get_risk_model()
    pairs = ensure_grid_zones(db, model.cell_size_m)
    lats = np.array([cell.centre[0] for cell, _ in pairs])
    lons = np.array([cell.centre[1] for cell, _ in pairs])
    past = np.array([model.past_rate(cell.name(model.cell_size_m)) for cell, _ in pairs])
    static = static_features(lats, lons, past)

    fallback_rain, fallback_temp = fallback_weather(day)
    if rain_mm is None and temp_max_c is None:
        weather_source = "fallback-climatology"
    elif rain_mm is not None and temp_max_c is not None:
        weather_source = "given"
    else:
        weather_source = "partly given, partly fallback"
    rain = fallback_rain if rain_mm is None else rain_mm
    temp = fallback_temp if temp_max_c is None else temp_max_c

    starts = [bin_start(day, b) for b in range(TIME_BINS)]
    zone_ids = [zone.id for _, zone in pairs]
    db.execute(  # replace earlier predictions of the same model for this day
        delete(RiskPrediction).where(
            RiskPrediction.zone_id.in_(zone_ids),
            RiskPrediction.time_bin.in_(starts),
            RiskPrediction.model_version == model.version,
        )
    )
    counts: Counter = Counter()
    rows = []
    for b, start in enumerate(starts):
        scores = np.clip(model.scores(feature_matrix(static, day, b, rain, temp)), 0.0, 1.0)
        for (_, zone), score in zip(pairs, scores, strict=True):
            level = level_from_score(float(score))
            counts[level.value] += 1
            rows.append(
                RiskPrediction(
                    zone_id=zone.id,
                    time_bin=start,
                    score=float(score),
                    level=level,
                    model_version=model.version,
                )
            )
    db.add_all(rows)
    db.flush()
    return PredictionSummary(
        model_version=model.version,
        day=day,
        time_bins=starts,
        cells=len(pairs),
        rows_written=len(rows),
        by_level={level.value: counts.get(level.value, 0) for level in RiskLevel},
        weather_source=weather_source,
    )


def effective_levels(db: Session, zones: list[RiskZone], at: datetime) -> dict[int, EffectiveLevel]:
    """The level of each zone at moment `at` (see module docstring)."""
    start = bin_start(*bin_of(at))
    end = start + timedelta(hours=BIN_HOURS)
    grid_ids = [z.id for z in zones if z.kind == ZoneKind.GRID]
    latest: dict[int, RiskPrediction] = {}
    if grid_ids:
        predictions = db.scalars(
            select(RiskPrediction)
            .where(RiskPrediction.zone_id.in_(grid_ids), RiskPrediction.time_bin == start)
            .order_by(RiskPrediction.created_at.desc(), RiskPrediction.id.desc())
        )
        for prediction in predictions:
            latest.setdefault(prediction.zone_id, prediction)

    result = {}
    for zone in zones:
        if zone.kind == ZoneKind.AREA:
            source = "fixed level" + (" (synthetic demo zone)" if zone.is_synthetic else "")
            result[zone.id] = EffectiveLevel(zone.base_level, source)
        elif zone.id in latest:
            p = latest[zone.id]
            result[zone.id] = EffectiveLevel(
                p.level,
                f"risk model {p.model_version} (synthetic training data) for "
                f"{start:%d %b %H:%M}-{end:%H:%M} IST",
                p.score,
            )
        else:
            result[zone.id] = EffectiveLevel(RiskLevel.LOW, "no prediction for this time")
    return result
