"""Notifications. In-app notifications are shown in the tourist app.

SMS and e-mail are SANDBOX channels only (Phase 5): they are written here and logged,
never sent to a real phone or mailbox.
"""

import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, text_enum


class NotificationChannel(enum.StrEnum):
    IN_APP = "in_app"
    SMS_SANDBOX = "sms_sandbox"
    EMAIL_SANDBOX = "email_sandbox"


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    # The app user who receives it (None for e.g. a sandbox SMS to an emergency contact).
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    recipient: Mapped[str | None] = mapped_column(String(254))  # sandbox phone / e-mail
    channel: Mapped[NotificationChannel] = mapped_column(text_enum(NotificationChannel, 20))
    kind: Mapped[str] = mapped_column(String(40))  # e.g. "geofence_alert"
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    incident_id: Mapped[int | None] = mapped_column(
        ForeignKey("incidents.id", ondelete="CASCADE"), index=True
    )
    zone_id: Mapped[int | None] = mapped_column(ForeignKey("risk_zones.id", ondelete="SET NULL"))
    simulated: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
