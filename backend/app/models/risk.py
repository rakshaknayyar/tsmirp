"""Risk zones: areas with a RELATIVE risk level, used for geofence alerts and map layers.

A risk level is a decision-support estimate, never a prediction that a crime will occur.
The demo zones are SYNTHETIC (see ml/data/synthetic_risk_zones_jaipur.json).
"""

import enum
from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import Boolean, DateTime, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, text_enum


class RiskLevel(enum.StrEnum):
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


# Geofence alerts are raised only for these levels.
ALERT_LEVELS = frozenset({RiskLevel.HIGH, RiskLevel.CRITICAL})


class RiskZone(Base):
    __tablename__ = "risk_zones"
    __table_args__ = (Index("ix_risk_zones_geom", "geom", postgresql_using="gist"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    geom: Mapped[str] = mapped_column(Geometry("POLYGON", srid=4326, spatial_index=False))
    base_level: Mapped[RiskLevel] = mapped_column(text_enum(RiskLevel, 10))
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=True)
    source: Mapped[str] = mapped_column(String(40))  # e.g. "synthetic-seed"
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
