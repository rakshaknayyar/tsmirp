"""Phase 9: GET /analytics/summary (plain incident counts for the dashboard)."""

from app.models.user import Role
from tests.conftest import auth_headers


def test_summary_counts_new_reports(client, users):
    tourist = auth_headers(client, users[Role.TOURIST])
    staff = auth_headers(client, users[Role.SUPERVISOR])
    before = client.get("/analytics/summary", headers=staff).json()

    client.post(
        "/incidents",
        headers=tourist,
        json={"description": "My bag was stolen", "category_code": "theft"},
    )
    client.post("/incidents", headers=tourist, json={"description": "Mera phone chori ho gaya"})
    client.post("/sos", headers=tourist, json={})
    after = client.get("/analytics/summary", headers=staff).json()

    assert after["total"] == before["total"] + 3
    assert after["sos"] == before["sos"] + 1
    assert after["by_category"].get("theft", 0) == before["by_category"].get("theft", 0) + 1
    assert after["by_language"].get("hi-Latn", 0) == before["by_language"].get("hi-Latn", 0) + 1
    # No text model in tests, so the uncategorised romanised report needs review.
    assert after["needs_review"] == before["needs_review"] + 1
    assert len(after["per_day"]) == 7
    assert after["per_day"][-1]["count"] >= 3  # today
    assert sum(day["count"] for day in after["per_day"]) == after["total"]
    assert sum(after["by_status"].values()) == after["total"]


def test_summary_rules(client, users):
    tourist = auth_headers(client, users[Role.TOURIST])
    operator = auth_headers(client, users[Role.OPERATOR])

    assert client.get("/analytics/summary").status_code == 401
    assert client.get("/analytics/summary", headers=tourist).status_code == 403
    assert client.get("/analytics/summary?days=0", headers=operator).status_code == 422
    assert client.get("/analytics/summary?days=91", headers=operator).status_code == 422
    assert client.get("/analytics/summary?days=30", headers=operator).json()["days"] == 30
