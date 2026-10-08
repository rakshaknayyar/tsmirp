"""Request and response shapes for the digital tourist ID (QR credential)."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CredentialOut(BaseModel):
    token: str  # the signed credential; the QR code contains exactly this text
    issued_at: datetime
    expires_at: datetime
    qr_svg: str  # the QR code as an SVG image
    note: str = (
        "Time-limited digital tourist ID, signed by the server. It contains your name and "
        "nationality only - no location. Staff can check it is genuine and not expired."
    )


class VerifyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str = Field(min_length=10, max_length=4000)


class VerifyResponse(BaseModel):
    valid: bool
    reason: str
    user_id: int | None
    full_name: str | None
    nationality: str | None
    issued_at: datetime | None
    expires_at: datetime | None
