"""The incident status lifecycle rules (no database needed)."""

import pytest

from app.models.incident import Incident, IncidentStatus
from app.services.incidents import ALLOWED_TRANSITIONS, InvalidTransition, change_status

S = IncidentStatus


def test_full_happy_path_is_allowed():
    path = [S.NEW, S.ACKNOWLEDGED, S.ASSIGNED, S.EN_ROUTE, S.RESOLVED, S.CLOSED]

    for current, following in zip(path, path[1:], strict=False):
        assert following in ALLOWED_TRANSITIONS[current]


def test_closed_is_final():
    assert ALLOWED_TRANSITIONS[S.CLOSED] == set()


def test_every_status_can_still_reach_closed():
    for start in S:
        reachable, frontier = {start}, [start]
        while frontier:
            for nxt in ALLOWED_TRANSITIONS[frontier.pop()]:
                if nxt not in reachable:
                    reachable.add(nxt)
                    frontier.append(nxt)
        assert S.CLOSED in reachable, f"{start} can never be closed"


def test_change_status_returns_old_status():
    incident = Incident(status=S.NEW)

    old = change_status(incident, S.ACKNOWLEDGED)

    assert old == S.NEW
    assert incident.status == S.ACKNOWLEDGED


@pytest.mark.parametrize(
    ("current", "target"),
    [(S.NEW, S.RESOLVED), (S.NEW, S.CLOSED), (S.CLOSED, S.NEW), (S.EN_ROUTE, S.NEW)],
)
def test_skipping_or_going_back_is_refused(current, target):
    with pytest.raises(InvalidTransition):
        change_status(Incident(status=current), target)


def test_assigned_cannot_be_set_directly():
    with pytest.raises(InvalidTransition):
        change_status(Incident(status=S.ACKNOWLEDGED), S.ASSIGNED)
