"""Risk zones and risk predictions.

A risk level is a RELATIVE decision-support estimate, never a prediction that a crime will
occur. Two kinds of zone:
- "area": hand-drawn zones with a fixed base_level (the SYNTHETIC demo zones);
- "grid": ~1 km grid cells whose level comes from the risk model (risk_predictions).
"""

import enum
from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, text_enum


class RiskLevel(enum.StrEnum):
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


# Geofence alerts are raised only for these levels.
ALERT_LEVELS = frozenset({RiskLevel.HIGH, RiskLevel.CRITICAL})


class ZoneKind(enum.StrEnum):
    AREA = "area"
    GRID = "grid"


class RiskZone(Base):
    __tablename__ = "risk_zones"
    __table_args__ = (Index("ix_risk_zones_geom", "geom", postgresql_using="gist"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    geom: Mapped[str] = mapped_column(Geometry("POLYGON", srid=4326, spatial_index=False))
    kind: Mapped[ZoneKind] = mapped_column(text_enum(ZoneKind, 10), default=ZoneKind.AREA)
    # For "area" zones the level; for "grid" cells only a fallback (LOW) when no prediction.
    base_level: Mapped[RiskLevel] = mapped_column(text_enum(RiskLevel, 10))
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=True)
    source: Mapped[str] = mapped_column(String(40))  # e.g. "synthetic-seed", "grid-1000m"
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RiskPrediction(Base):
    """The risk model's score for one zone (grid cell) and one 6-hour time bin."""

    __tablename__ = "risk_predictions"
    __table_args__ = (UniqueConstraint("zone_id", "time_bin", "model_version"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    zone_id: Mapped[int] = mapped_column(
        ForeignKey("risk_zones.id", ondelete="CASCADE"), index=True
    )
    time_bin: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)  # bin start
    score: Mapped[float] = mapped_column(Float)  # calibrated, in [0, 1]
    level: Mapped[RiskLevel] = mapped_column(text_enum(RiskLevel, 10))
    model_version: Mapped[str] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
