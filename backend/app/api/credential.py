"""Digital tourist ID (replaces the out-of-scope blockchain ID; see app/services/credential.py).

- GET  /tourist/credential   tourist: get a fresh signed credential and its QR code
- POST /credential/verify    staff: check that a credential is genuine and not expired
Both are written to the audit log.
"""

from fastapi import APIRouter

from app.api.deps import DbSession, StaffUser, TouristUser
from app.schemas.credential import CredentialOut, VerifyRequest, VerifyResponse
from app.services.audit import record_event
from app.services.credential import issue_credential, verify_credential

router = APIRouter(tags=["credential"])


@router.get("/tourist/credential", response_model=CredentialOut)
def get_credential(user: TouristUser, db: DbSession) -> CredentialOut:
    issued = issue_credential(db, user)
    record_event(
        db,
        "credential.issued",
        actor_user_id=user.id,
        target_type="user",
        target_id=user.id,
        details={"expires_at": issued.expires_at.isoformat()},
    )
    db.commit()
    return CredentialOut(
        token=issued.token,
        issued_at=issued.issued_at,
        expires_at=issued.expires_at,
        qr_svg=issued.qr_svg,
    )


@router.post("/credential/verify", response_model=VerifyResponse)
def verify(body: VerifyRequest, staff: StaffUser, db: DbSession) -> VerifyResponse:
    result = verify_credential(db, body.token)
    record_event(
        db,
        "credential.verified",
        actor_user_id=staff.id,
        target_type="user",
        target_id=result.user_id,
        details={"valid": result.valid},  # the token itself is not stored
    )
    db.commit()
    return VerifyResponse(
        valid=result.valid,
        reason=result.reason,
        user_id=result.user_id,
        full_name=result.full_name,
        nationality=result.nationality,
        issued_at=result.issued_at,
        expires_at=result.expires_at,
    )
