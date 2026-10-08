"""Risk model: shared features, synthetic incidents, training, /risk/predict and the use of
predicted levels in the map, the geofence and the severity rules.

A tiny model (3 km cells, 60 days, fallback weather - no network) is trained once per run.
"""

import sys
from datetime import UTC, date, datetime, timedelta

import numpy as np
import pytest
from sqlalchemy import func, select

from app.core.config import REPO_ROOT, settings
from app.ml import risk_model
from app.ml.risk_features import (
    FEATURE_NAMES,
    IST,
    LANDMARKS,
    bin_of,
    bin_start,
    grid_cells,
    level_name,
    static_features,
)
from app.models.audit import AuditLog
from app.models.risk import RiskLevel, RiskPrediction, ZoneKind
from app.models.user import Role
from app.services.risk import effective_levels, level_from_score
from tests.conftest import auth_headers
from tests.test_geofence import add_zone

sys.path.insert(0, str(REPO_ROOT))  # so the ml/ folder can be imported
from ml.incident_data import HOTSPOTS, generate_incidents, label_matrix  # noqa: E402
from ml.train_risk_model import RiskTrainConfig, train  # noqa: E402
from ml.weather import fallback_series  # noqa: E402

TINY = RiskTrainConfig(
    n_days=60, cell_size_m=3000, weather_source="fallback", rf_trees=10, cv_folds=3, block_cells=2
)
HAWA_MAHAL = LANDMARKS["Hawa Mahal"]


@pytest.fixture(scope="session")
def trained(tmp_path_factory):
    root = tmp_path_factory.mktemp("risk")
    return root, train(TINY, root / "artefacts", root / "synthetic", report_path=None)


@pytest.fixture
def model(trained, monkeypatch):
    root, _ = trained
    monkeypatch.setattr(settings, "risk_model_dir", root / "artefacts")
    risk_model.reset_cache()
    yield
    risk_model.reset_cache()


# ---------- shared features ----------


def test_grid_covers_the_demo_area_with_unique_names():
    cells = grid_cells(1000)

    assert len({c.name(1000) for c in cells}) == len(cells)
    assert min(c.south for c in cells) == pytest.approx(26.80)
    assert max(c.north for c in cells) == pytest.approx(27.00)
    assert max(c.east for c in cells) == pytest.approx(75.90)


def test_static_features_near_a_landmark():
    features = static_features(np.array([HAWA_MAHAL[0]]), np.array([HAWA_MAHAL[1]]), np.zeros(1))

    assert features.shape == (1, 4)
    assert features[0, 0] == pytest.approx(0.0, abs=1e-6)  # distance to nearest landmark
    assert features[0, 1] >= 2  # Hawa Mahal and City Palace are within 1 km


def test_level_thresholds():
    t = (0.25, 0.50, 0.75)

    assert [level_name(s, t) for s in (0.0, 0.249, 0.25, 0.5, 0.749, 0.75, 1.0)] == [
        "LOW", "LOW", "MODERATE", "HIGH", "HIGH", "CRITICAL", "CRITICAL",
    ]  # fmt: skip


def test_time_bins_use_india_time():
    # 20:30 UTC on 1 Jan = 02:00 IST on 2 Jan -> bin 0 of 2 Jan.
    day, time_bin = bin_of(datetime(2026, 1, 1, 20, 30, tzinfo=UTC))

    assert (day, time_bin) == (date(2026, 1, 2), 0)
    assert bin_start(day, 3) == datetime(2026, 1, 2, 18, 0, tzinfo=IST)


# ---------- synthetic incidents ----------


def test_generator_is_deterministic_labelled_and_consistent():
    cells = grid_cells(3000)
    start, n_days = date(2025, 1, 1), 10
    weather = fallback_series(start, n_days)

    first = generate_incidents(cells, start, n_days, weather, seed=1)
    second = generate_incidents(cells, start, n_days, weather, seed=1)
    labels = label_matrix(first, cells, start, n_days)

    assert first == second
    assert first and all(i.synthetic for i in first)
    assert labels.sum() <= len(first)  # several incidents can share a cell-bin
    assert labels.sum() > 0


def test_some_hotspots_are_hidden_from_the_model():
    hotspot_places = {(round(h.lat, 2), round(h.lon, 2)) for h in HOTSPOTS}
    landmark_places = {(round(lat, 2), round(lon, 2)) for lat, lon in LANDMARKS.values()}

    assert len(hotspot_places - landmark_places) >= 3


# ---------- training ----------


def test_training_writes_artefacts_with_honest_metadata(trained):
    root, result = trained
    version = (root / "artefacts" / "LATEST").read_text()
    folder = root / "artefacts" / version

    assert version == result["version"]
    assert all((folder / f).is_file() for f in ["model.joblib", "metadata.json", "metrics.json"])
    assert result["weather_source"] == "fallback-climatology"
    assert set(result["test"]) >= {"roc_auc", "pr_auc", "brier", "confusion_matrix", "levels"}
    period = result["period"]
    assert period["train_until"] < period["validation_until"] < period["test_until"]
    assert {row["model"] for row in result["cv"]} == {"logistic_regression", "random_forest"}


def test_training_is_reproducible(trained, tmp_path):
    _, first = trained

    second = train(TINY, tmp_path / "artefacts", tmp_path / "synthetic", report_path=None)

    assert second["version"] == first["version"]
    assert second["test"]["pr_auc"] == first["test"]["pr_auc"]


# ---------- POST /risk/predict ----------


def test_predict_stores_levels_with_model_version(client, db, users, model, trained):
    _, result = trained
    headers = auth_headers(client, users[Role.OPERATOR])

    response = client.post("/risk/predict", headers=headers, json={"date": "2026-01-15"})

    assert response.status_code == 200
    body = response.json()
    assert body["model_version"] == result["version"]
    assert body["rows_written"] == body["cells"] * 4
    assert sum(body["by_level"].values()) == body["rows_written"]
    assert "SYNTHETIC" in body["note"]
    predictions = db.scalars(
        select(RiskPrediction).where(RiskPrediction.model_version == result["version"])
    ).all()
    assert len(predictions) == body["rows_written"]
    assert all(p.level == level_from_score(p.score) for p in predictions)
    assert db.scalar(select(AuditLog).where(AuditLog.action == "risk.predicted"))


def test_predicting_twice_replaces_instead_of_duplicating(client, db, users, model):
    headers = auth_headers(client, users[Role.OPERATOR])

    client.post("/risk/predict", headers=headers, json={"date": "2026-01-15"})
    second = client.post("/risk/predict", headers=headers, json={"date": "2026-01-15"}).json()

    # Count only this model's rows: the database may hold real predictions from other runs.
    count = db.scalar(
        select(func.count())
        .select_from(RiskPrediction)
        .where(RiskPrediction.model_version == second["model_version"])
    )
    assert count == second["rows_written"]


def test_predict_rules(client, users):
    tourist = auth_headers(client, users[Role.TOURIST])
    operator = auth_headers(client, users[Role.OPERATOR])

    assert client.post("/risk/predict", headers=tourist, json={}).status_code == 403
    assert client.post("/risk/predict", headers=operator, json={}).status_code == 503  # no model
    bad_weather = {"rain_mm": -1}
    assert client.post("/risk/predict", headers=operator, json=bad_weather).status_code == 422


# ---------- predicted levels in use ----------


def _grid_zone_with_prediction(db, level: RiskLevel, at: datetime):
    zone = add_zone(db, "Test grid cell", RiskLevel.LOW)
    zone.kind = ZoneKind.GRID
    db.add(
        RiskPrediction(
            zone_id=zone.id,
            time_bin=bin_start(*bin_of(at)),
            score={"LOW": 0.1, "MODERATE": 0.3, "HIGH": 0.6, "CRITICAL": 0.9}[level.value],
            level=level,
            model_version="riskmodel-v1-test000000",
        )
    )
    db.commit()
    return zone


def test_effective_level_comes_from_the_current_bin_only(db):
    now = datetime.now(UTC)
    zone = _grid_zone_with_prediction(db, RiskLevel.CRITICAL, now)

    current = effective_levels(db, [zone], now)[zone.id]
    later = effective_levels(db, [zone], now + timedelta(hours=7))[zone.id]

    assert current.level == RiskLevel.CRITICAL and "synthetic" in current.source
    assert later.level == RiskLevel.LOW and later.source == "no prediction for this time"


def test_predicted_critical_cell_triggers_geofence_alert(client, db, users, monkeypatch):
    monkeypatch.setattr(settings, "geofence_dwell_seconds", 0)
    zone = _grid_zone_with_prediction(db, RiskLevel.CRITICAL, datetime.now(UTC))
    headers = auth_headers(client, users[Role.TOURIST])
    client.put("/tourist/consent", headers=headers, json={"location_consent": True})

    body = client.post(
        "/tourist/location", headers=headers, json={"lat": 12.0, "lon": 12.0, "accuracy_m": 10}
    ).json()

    assert [z["level"] for z in body["inside_zones"] if z["id"] == zone.id] == ["CRITICAL"]
    assert any("risk model" in alert["body"] for alert in body["alerts"])


def test_grid_cell_without_prediction_does_not_alert(client, db, users, monkeypatch):
    monkeypatch.setattr(settings, "geofence_dwell_seconds", 0)
    zone = add_zone(db, "Test grid cell", RiskLevel.LOW)
    zone.kind = ZoneKind.GRID
    db.commit()
    headers = auth_headers(client, users[Role.TOURIST])
    client.put("/tourist/consent", headers=headers, json={"location_consent": True})

    body = client.post(
        "/tourist/location", headers=headers, json={"lat": 12.0, "lon": 12.0, "accuracy_m": 10}
    ).json()

    assert body["alerts"] == []


def test_map_shows_predicted_level_and_its_source(client, db, users):
    zone = _grid_zone_with_prediction(db, RiskLevel.HIGH, datetime.now(UTC))
    headers = auth_headers(client, users[Role.TOURIST])

    features = client.get("/risk-zone?bbox=11.9,11.9,12.1,12.1", headers=headers).json()["features"]

    props = next(f["properties"] for f in features if f["properties"]["id"] == zone.id)
    assert (props["kind"], props["level"], props["score"]) == ("grid", "HIGH", 0.6)
    assert "risk model" in props["level_source"]


def test_report_inside_predicted_high_cell_gets_high_severity(client, db, users):
    _grid_zone_with_prediction(db, RiskLevel.HIGH, datetime.now(UTC))
    headers = auth_headers(client, users[Role.TOURIST])
    client.put("/tourist/consent", headers=headers, json={"location_consent": True})

    body = client.post(
        "/incidents",
        headers=headers,
        json={
            "description": "There is an unattended bag here",
            "category_code": "suspicious_activity",  # LOW by default
            "location": {"lat": 12.0, "lon": 12.0, "accuracy_m": 10},
        },
    ).json()

    assert body["severity"] == "HIGH"


def test_metadata_lets_the_app_rebuild_the_same_features(trained):
    import json

    root, result = trained
    metadata = json.loads((root / "artefacts" / result["version"] / "metadata.json").read_text())

    assert set(metadata["feature_names"]) <= set(FEATURE_NAMES)
    cell_names = {c.name(TINY.cell_size_m) for c in grid_cells(TINY.cell_size_m)}
    assert set(metadata["cell_past_rates"]) == cell_names
    assert metadata["synthetic_training_data"] is True
