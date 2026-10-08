"""Hash-chained audit log: links, verification, and tamper detection."""

from sqlalchemy import select, text

from app.models.audit import AuditLog
from app.models.user import Role
from app.services.audit import record_event, verify_chain
from tests.conftest import auth_headers, make_user


def _add_events(db, count: int) -> list[AuditLog]:
    events = [record_event(db, "test.event", details={"n": i}) for i in range(count)]
    db.commit()
    return events


def test_each_row_points_to_the_previous_row(db):
    events = _add_events(db, 3)

    assert events[1].prev_hash == events[0].row_hash
    assert events[2].prev_hash == events[1].row_hash


def test_untouched_chain_verifies(db):
    _add_events(db, 3)

    assert verify_chain(db)["valid"] is True


def test_editing_a_row_is_detected(db):
    events = _add_events(db, 3)

    db.execute(
        text("UPDATE audit_logs SET details = '{\"n\": 999}' WHERE id = :id"),
        {"id": events[1].id},
    )
    db.expire_all()  # forget cached rows so the edited values are read back
    result = verify_chain(db)

    assert result["valid"] is False
    assert result["first_broken_id"] == events[1].id


def test_deleting_a_row_is_detected(db):
    events = _add_events(db, 3)

    db.execute(text("DELETE FROM audit_logs WHERE id = :id"), {"id": events[1].id})
    db.expire_all()
    result = verify_chain(db)

    assert result["valid"] is False
    assert result["first_broken_id"] == events[2].id


def test_verify_endpoint_reports_valid_chain(client, users):
    headers = auth_headers(client, users[Role.SUPERVISOR])

    response = client.get("/audit-logs/verify", headers=headers)

    assert response.status_code == 200
    assert response.json()["valid"] is True


def test_audit_log_never_contains_passwords(client, db):
    tourist = make_user(db, Role.TOURIST)
    auth_headers(client, tourist)  # logs in, which writes an audit row

    all_details = db.scalars(select(AuditLog.details)).all()

    assert "correct-horse-battery" not in str(all_details)
