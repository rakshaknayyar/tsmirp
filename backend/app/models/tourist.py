"""Tourist profile (with location consent) and emergency contacts."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class TouristProfile(Base):
    __tablename__ = "tourist_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    nationality: Mapped[str | None] = mapped_column(String(60))
    phone: Mapped[str | None] = mapped_column(String(20))
    preferred_language: Mapped[str] = mapped_column(String(10), default="en")
    # Location is collected only while this is True. Off by default; can be revoked any time.
    location_consent: Mapped[bool] = mapped_column(Boolean, default=False)
    # When the tourist last granted or revoked consent (None = never decided).
    consent_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class EmergencyContact(Base):
    __tablename__ = "emergency_contacts"

    id: Mapped[int] = mapped_column(primary_key=True)
    tourist_profile_id: Mapped[int] = mapped_column(
        ForeignKey("tourist_profiles.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(120))
    phone: Mapped[str] = mapped_column(String(20))
    relation: Mapped[str | None] = mapped_column(String(40))  # e.g. "parent", "friend"
