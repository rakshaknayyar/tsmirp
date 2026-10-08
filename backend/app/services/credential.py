"""Digital tourist ID: a time-limited, signed credential shown as a QR code.

This replaces the blockchain digital ID of the original problem statement (out of scope):
- The credential is a JWT signed with the server's secret (type "tourist_credential"). It holds
  only the tourist's user id, name and nationality, and an expiry date - no location, phone
  number or other personal data.
- Anyone can READ a JWT, but nobody can CHANGE it without the secret: a changed or expired
  credential fails verification.
- Staff verify it with POST /credential/verify (in a real deployment a scanner app would read
  the QR code; here the token text is pasted). The verification also checks that the account
  still exists and is active.
Limitation: there is no revocation list, so a credential stays valid until it expires unless
the account is deactivated.
"""

import io
from dataclasses import dataclass
from datetime import UTC, datetime

import segno
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import CREDENTIAL, TokenError, create_credential_token, decode_token
from app.models.tourist import TouristProfile
from app.models.user import Role, User


@dataclass(frozen=True)
class IssuedCredential:
    token: str
    issued_at: datetime
    expires_at: datetime
    qr_svg: str


@dataclass(frozen=True)
class VerificationResult:
    valid: bool
    reason: str
    user_id: int | None = None
    full_name: str | None = None
    nationality: str | None = None
    issued_at: datetime | None = None
    expires_at: datetime | None = None


def qr_svg(text: str) -> str:
    """The text as a QR code: a standalone SVG image (with xmlns, so a browser can show it as
    an <img>). Error correction level M lets the code be read even if ~15 % is damaged."""
    buffer = io.BytesIO()
    segno.make(text, error="m").save(buffer, kind="svg", xmldecl=False, scale=4, border=2)
    return buffer.getvalue().decode("utf-8")


def issue_credential(db: Session, user: User) -> IssuedCredential:
    profile = db.scalar(select(TouristProfile).where(TouristProfile.user_id == user.id))
    claims = {"name": user.full_name, "nationality": profile.nationality if profile else None}
    token = create_credential_token(user.id, claims)
    payload = decode_token(token, CREDENTIAL)
    return IssuedCredential(
        token=token,
        issued_at=datetime.fromtimestamp(payload["iat"], UTC),
        expires_at=datetime.fromtimestamp(payload["exp"], UTC),
        qr_svg=qr_svg(token),
    )


def verify_credential(db: Session, token: str) -> VerificationResult:
    try:
        payload = decode_token(token, CREDENTIAL)
    except TokenError:
        # Expired, changed, signed with another key, or another kind of token.
        return VerificationResult(False, "Not a valid credential (expired or altered)")
    user = db.get(User, int(payload["sub"]))
    if user is None or not user.is_active or user.role != Role.TOURIST:
        return VerificationResult(False, "The tourist account no longer exists or is inactive")
    return VerificationResult(
        valid=True,
        reason="Valid credential",
        user_id=user.id,
        full_name=payload.get("name"),
        nationality=payload.get("nationality"),
        issued_at=datetime.fromtimestamp(payload["iat"], UTC),
        expires_at=datetime.fromtimestamp(payload["exp"], UTC),
    )
