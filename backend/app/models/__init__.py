"""Importing every model here registers its table on Base.metadata, which Alembic reads."""

from app.models.audit import AuditLog
from app.models.base import Base
from app.models.tourist import EmergencyContact, TouristProfile
from app.models.user import Role, User

__all__ = ["AuditLog", "Base", "EmergencyContact", "Role", "TouristProfile", "User"]
