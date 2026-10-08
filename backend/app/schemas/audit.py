"""Response shapes for the audit log."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    actor_user_id: int | None
    action: str
    target_type: str | None
    target_id: str | None
    details: dict
    prev_hash: str
    row_hash: str


class ChainVerification(BaseModel):
    valid: bool
    checked: int
    first_broken_id: int | None
