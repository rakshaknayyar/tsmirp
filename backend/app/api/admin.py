"""Staff management and audit log routes.

- POST /admin/users        administrator only: create operator/supervisor/administrator accounts
- GET  /audit-logs         supervisor or administrator: newest audit entries
- GET  /audit-logs/verify  supervisor or administrator: check the hash chain is intact
"""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from app.api.deps import AdminUser, AuditReader, DbSession
from app.models.audit import AuditLog
from app.models.user import User
from app.schemas.audit import AuditLogOut, ChainVerification
from app.schemas.auth import StaffCreateRequest, UserOut
from app.services.audit import record_event, verify_chain
from app.services.users import EmailAlreadyRegistered, create_user

router = APIRouter(tags=["administration"])


@router.post("/admin/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_staff_user(body: StaffCreateRequest, admin: AdminUser, db: DbSession) -> User:
    try:
        user = create_user(
            db,
            email=body.email,
            password=body.password,
            full_name=body.full_name,
            role=body.role,
        )
    except EmailAlreadyRegistered:
        raise HTTPException(status.HTTP_409_CONFLICT, "E-mail already registered") from None
    record_event(
        db,
        "user.created_by_admin",
        actor_user_id=admin.id,
        target_type="user",
        target_id=user.id,
        details={"role": body.role.value},
    )
    db.commit()
    return user


@router.get("/audit-logs", response_model=list[AuditLogOut])
def list_audit_logs(
    reader: AuditReader,
    db: DbSession,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[AuditLog]:
    return list(db.scalars(select(AuditLog).order_by(AuditLog.id.desc()).limit(limit)))


@router.get("/audit-logs/verify", response_model=ChainVerification)
def verify_audit_chain(reader: AuditReader, db: DbSession) -> dict:
    return verify_chain(db)
