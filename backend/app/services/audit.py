"""Hash-chained audit log.

Every row stores the hash of the row before it (prev_hash) and its own hash (row_hash),
computed from its contents plus prev_hash. Changing or deleting an old row breaks the chain
from that point on, which verify_chain() detects.
This makes tampering DETECTABLE; it does not make it impossible.
"""

import hashlib
import json
from datetime import UTC, datetime

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models.audit import AuditLog

GENESIS_HASH = "0" * 64  # "previous hash" of the very first row
AUDIT_LOCK_ID = 7_301_001  # any fixed number; names the PostgreSQL advisory lock below


def compute_hash(
    prev_hash: str,
    created_at: datetime,
    actor_user_id: int | None,
    action: str,
    target_type: str | None,
    target_id: str | None,
    details: dict,
) -> str:
    # sort_keys + fixed separators = the same input always gives exactly the same text.
    canonical = json.dumps(
        {
            "prev_hash": prev_hash,
            "created_at": created_at.astimezone(UTC).isoformat(),
            "actor_user_id": actor_user_id,
            "action": action,
            "target_type": target_type,
            "target_id": target_id,
            "details": details,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _hash_of(row: AuditLog) -> str:
    return compute_hash(
        row.prev_hash,
        row.created_at,
        row.actor_user_id,
        row.action,
        row.target_type,
        row.target_id,
        row.details,
    )


def record_event(
    db: Session,
    action: str,
    *,
    actor_user_id: int | None = None,
    target_type: str | None = None,
    target_id: int | str | None = None,
    details: dict | None = None,
) -> AuditLog:
    """Append one row to the chain. The caller commits (together with the action itself)."""
    # Only one transaction at a time may append; otherwise two new rows could both point to
    # the same previous row and fork the chain. The lock is released at commit/rollback.
    db.execute(text("SELECT pg_advisory_xact_lock(:lock_id)"), {"lock_id": AUDIT_LOCK_ID})

    last_hash = db.scalar(select(AuditLog.row_hash).order_by(AuditLog.id.desc()).limit(1))
    entry = AuditLog(
        created_at=datetime.now(UTC),
        actor_user_id=actor_user_id,
        action=action,
        target_type=target_type,
        target_id=str(target_id) if target_id is not None else None,
        details=details or {},
        prev_hash=last_hash or GENESIS_HASH,
    )
    entry.row_hash = _hash_of(entry)
    db.add(entry)
    db.flush()
    return entry


def verify_chain(db: Session) -> dict:
    """Recompute every hash in order. Returns where the chain first breaks, if anywhere."""
    expected_prev = GENESIS_HASH
    checked = 0
    for row in db.scalars(select(AuditLog).order_by(AuditLog.id)):
        if row.prev_hash != expected_prev or _hash_of(row) != row.row_hash:
            return {"valid": False, "checked": checked, "first_broken_id": row.id}
        expected_prev = row.row_hash
        checked += 1
    return {"valid": True, "checked": checked, "first_broken_id": None}
