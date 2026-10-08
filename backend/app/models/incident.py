"""Incident categories, incidents, and incident locations (PostGIS points)."""

import enum
from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Severity(enum.StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class IncidentStatus(enum.StrEnum):
    NEW = "NEW"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    ASSIGNED = "ASSIGNED"
    EN_ROUTE = "EN_ROUTE"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


def _as_text(enum_class: type[enum.Enum], length: int) -> Enum:
    # Stored as plain text; the CHECK constraints in migration 0003 restrict the values.
    return Enum(
        enum_class,
        native_enum=False,
        length=length,
        values_callable=lambda members: [m.value for m in members],
    )


class IncidentCategory(Base):
    """The 9 categories, each with a fixed suggested department (seeded by migration 0003)."""

    __tablename__ = "incident_categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(30), unique=True)  # e.g. "theft"
    name: Mapped[str] = mapped_column(String(60))  # e.g. "Theft"
    department: Mapped[str] = mapped_column(String(40))  # e.g. "Police"


class Incident(Base):
    __tablename__ = "incidents"

    id: Mapped[int] = mapped_column(primary_key=True)
    # SET NULL: if an account is removed later (retention), the incident record remains.
    reporter_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    category_id: Mapped[int | None] = mapped_column(ForeignKey("incident_categories.id"))
    description: Mapped[str] = mapped_column(Text)
    language: Mapped[str] = mapped_column(String(10), default="en")
    severity: Mapped[Severity] = mapped_column(_as_text(Severity, 10), default=Severity.MEDIUM)
    status: Mapped[IncidentStatus] = mapped_column(
        _as_text(IncidentStatus, 15), default=IncidentStatus.NEW, index=True
    )
    is_sos: Mapped[bool] = mapped_column(Boolean, default=False)
    # Classifier confidence in [0, 1]; empty until the classifier exists (Phase 6).
    confidence: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class IncidentLocation(Base):
    __tablename__ = "incident_locations"
    # GiST index = spatial index, makes "what is near / inside this area" queries fast.
    __table_args__ = (Index("ix_incident_locations_geom", "geom", postgresql_using="gist"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    incident_id: Mapped[int] = mapped_column(
        ForeignKey("incidents.id", ondelete="CASCADE"), index=True
    )
    # EPSG:4326 = ordinary GPS latitude/longitude. Note PostGIS points are (lon, lat).
    geom: Mapped[str] = mapped_column(Geometry("POINT", srid=4326, spatial_index=False))
    accuracy_m: Mapped[float | None] = mapped_column(Float)  # GPS accuracy radius in metres
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
