"""Response resources (police stations, hospitals, fire stations) and their assignments."""

import enum
from datetime import datetime

from geoalchemy2 import Geography
from sqlalchemy import DateTime, Float, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, text_enum


class ResourceType(enum.StrEnum):
    POLICE_STATION = "police_station"
    HOSPITAL = "hospital"
    FIRE_STATION = "fire_station"


class Availability(enum.StrEnum):
    """SIMULATED availability. The prototype has no live link to real resources."""

    AVAILABLE = "AVAILABLE"
    BUSY = "BUSY"
    OFFLINE = "OFFLINE"


class AssignmentStatus(enum.StrEnum):
    ACTIVE = "ACTIVE"
    RELEASED = "RELEASED"


class ResponseResource(Base):
    __tablename__ = "response_resources"
    # GiST index on the geography column: makes nearest-neighbour (<->) search fast.
    __table_args__ = (Index("ix_response_resources_geog", "geog", postgresql_using="gist"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    resource_type: Mapped[ResourceType] = mapped_column(text_enum(ResourceType, 20), index=True)
    # Geography (not geometry): distances come out in metres on the curved Earth.
    geog: Mapped[str] = mapped_column(Geography("POINT", srid=4326, spatial_index=False))
    source: Mapped[str] = mapped_column(String(20))  # "osm" or "manual"
    source_ref: Mapped[str | None] = mapped_column(String(40), unique=True)  # e.g. "node/123"
    capabilities: Mapped[list] = mapped_column(JSONB, default=list)  # e.g. ["emergency"]
    availability_sim: Mapped[Availability] = mapped_column(
        text_enum(Availability, 10), default=Availability.AVAILABLE
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ResponseAssignment(Base):
    """A SIMULATED dispatch: an operator assigned this resource to this incident."""

    __tablename__ = "response_assignments"

    id: Mapped[int] = mapped_column(primary_key=True)
    incident_id: Mapped[int] = mapped_column(
        ForeignKey("incidents.id", ondelete="CASCADE"), index=True
    )
    resource_id: Mapped[int] = mapped_column(ForeignKey("response_resources.id"), index=True)
    assigned_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    # Straight-line distance at the moment of assignment (None if the location was not visible).
    distance_m: Mapped[float | None] = mapped_column(Float)
    status: Mapped[AssignmentStatus] = mapped_column(
        text_enum(AssignmentStatus, 10), default=AssignmentStatus.ACTIVE
    )
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    note: Mapped[str | None] = mapped_column(String(500))
