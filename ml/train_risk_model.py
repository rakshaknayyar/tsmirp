"""Train and evaluate the risk model (grid cell x 6-hour time bin).

Run from the repository root with the backend's Python (one command, fixed seeds):

    python -m ml.train_risk_model

Steps:
1. Daily weather (Open-Meteo archive, cached; approximate fallback table if unavailable).
2. SYNTHETIC incidents for one year (ml/incident_data.py), turned into labels:
   label = 1 if at least one incident happened in the cell during the bin.
3. Features from app/ml/risk_features.py (the SAME code the API uses).
4. Chronological split: first 70 % of days = train, next 15 % = validation, last 15 % = test.
5. Stage 1 - algorithm: blocked spatial cross-validation on the training period (cells
   grouped into 4 x 4 blocks), place + time features only: logistic regression (baseline) vs
   random forest (primary), both with class weights. Choose the SIMPLEST model whose mean
   PR-AUC is within one standard deviation of the best.
6. Stage 2 - history feature: refit the chosen algorithm with and without "cell_past_rate"
   (the cell's incident rate in the training period) and keep it only if the VALIDATION
   PR-AUC improves by at least MIN_GAIN. (Spatial CV cannot judge this feature: a past rate
   does not exist for an unseen place.)
7. Refit, calibrate the probabilities (isotonic) on the validation period, and pick the
   decision threshold that maximises F1 on the validation period.
8. Evaluate on the test period; compare with a "historical rate of the cell" baseline.
9. Save versioned artefacts and write ml/reports/risk_model.md.

Not used: SMOTE (class weights instead); XGBoost (not evaluated in this prototype).
All results are on SYNTHETIC data and do NOT show real-world accuracy.
"""

import hashlib
import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from pathlib import Path

import joblib
import numpy as np
import sklearn
from sklearn.base import clone
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import RandomForestClassifier
from sklearn.frozen import FrozenEstimator
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    classification_report,
    confusion_matrix,
    precision_recall_curve,
    roc_auc_score,
)
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from app.ml.risk_features import (
    FEATURE_NAMES,
    TIME_BINS,
    columns,
    feature_matrix,
    grid_cells,
    level_name,
    static_features,
)
from ml.incident_data import CATEGORIES, generate_incidents, label_matrix, write_csv
from ml.weather import load_weather

REPO_ROOT = Path(__file__).resolve().parents[1]
TRAIN_FRACTION, VALIDATION_FRACTION = 0.70, 0.15
LEVELS = ["LOW", "MODERATE", "HIGH", "CRITICAL"]
PLACE_TIME_FEATURES = [name for name in FEATURE_NAMES if name != "cell_past_rate"]
MIN_GAIN = 0.01  # assumption: smallest validation PR-AUC gain worth an extra feature
DEVELOPMENT_HISTORY = [
    "First run (place + time features only, logistic regression chosen): test PR-AUC 0.185 "
    "vs 0.234 for the 'cell's historical rate' baseline, i.e. worse than the baseline, "
    "because three synthetic hotspots are hidden from the landmark features. The test "
    "period was therefore looked at once during development.",
    "Change made because of it: the cell's training-period incident rate was offered as an "
    "extra feature, kept only if it improves the VALIDATION PR-AUC (stage 2).",
]


@dataclass(frozen=True)
class RiskTrainConfig:
    start: date = date(2024, 10, 1)
    n_days: int = 365
    cell_size_m: int = 1000
    seed: int = 42
    weather_source: str = "auto"  # "auto" (Open-Meteo, else fallback) or "fallback"
    rf_trees: int = 150
    cv_folds: int = 5
    block_cells: int = 4
    # Initial level thresholds from the brief (configurable).
    level_thresholds: tuple[float, float, float] = field(default=(0.25, 0.50, 0.75))


def build_dataset(cells, start, n_days, weather, labels, past_rates):
    lats = np.array([c.centre[0] for c in cells])
    lons = np.array([c.centre[1] for c in cells])
    static = static_features(lats, lons, past_rates)
    blocks_x, blocks_y = [], []
    for d in range(n_days):
        day = start + timedelta(days=d)
        rain, temp = weather[day]
        for b in range(TIME_BINS):
            blocks_x.append(feature_matrix(static, day, b, rain, temp))
            blocks_y.append(labels[:, d, b])
    n_cells = len(cells)
    x = np.vstack(blocks_x)
    y = np.concatenate(blocks_y).astype(np.int8)
    day_index = np.repeat(np.arange(n_days), TIME_BINS * n_cells)
    cell_index = np.tile(np.arange(n_cells), n_days * TIME_BINS)
    return x, y, day_index, cell_index


def candidates(config: RiskTrainConfig) -> dict:
    """Listed from simplest to most complex."""
    return {
        "logistic_regression": make_pipeline(
            StandardScaler(),
            LogisticRegression(class_weight="balanced", max_iter=2000),
        ),
        "random_forest": RandomForestClassifier(
            n_estimators=config.rf_trees,
            min_samples_leaf=50,
            max_features="sqrt",
            max_samples=0.3,
            class_weight="balanced_subsample",
            n_jobs=-1,
            random_state=config.seed,
        ),
    }


def spatial_blocks(cells, block_cells: int) -> np.ndarray:
    """Block id per cell: cells grouped into block_cells x block_cells squares."""
    width = max(c.col for c in cells) // block_cells + 1
    return np.array([(c.row // block_cells) * width + c.col // block_cells for c in cells])


def cross_validate(models: dict, x, y, groups, folds: int) -> list[dict]:
    table = []
    for name, model in models.items():
        pr_aucs, roc_aucs = [], []
        for fit_idx, val_idx in GroupKFold(n_splits=folds).split(x, y, groups):
            fitted = clone(model).fit(x[fit_idx], y[fit_idx])
            scores = fitted.predict_proba(x[val_idx])[:, 1]
            pr_aucs.append(average_precision_score(y[val_idx], scores))
            roc_aucs.append(roc_auc_score(y[val_idx], scores))
        table.append(
            {
                "model": name,
                "pr_auc_mean": float(np.mean(pr_aucs)),
                "pr_auc_std": float(np.std(pr_aucs)),
                "roc_auc_mean": float(np.mean(roc_aucs)),
            }
        )
    return table


def choose(table: list[dict], order: list[str]) -> str:
    best = max(table, key=lambda r: r["pr_auc_mean"])
    good = [r for r in table if r["pr_auc_mean"] >= best["pr_auc_mean"] - best["pr_auc_std"]]
    return min(good, key=lambda r: order.index(r["model"]))["model"]


def best_f1_threshold(y, scores) -> float:
    precision, recall, thresholds = precision_recall_curve(y, scores)
    f1 = 2 * precision * recall / np.maximum(precision + recall, 1e-12)
    return float(thresholds[int(np.argmax(f1[:-1]))])


def importances(model, name: str, feature_names: list[str]) -> list[tuple[str, float]]:
    if name == "random_forest":
        values = model.feature_importances_
    else:
        values = np.abs(model[-1].coef_[0])  # size of the standardised coefficients
    return sorted(zip(feature_names, map(float, values), strict=True), key=lambda p: -p[1])


def evaluate(scores, y, threshold, thresholds, baseline_scores, uncalibrated_scores) -> dict:
    predicted = (scores >= threshold).astype(int)
    levels = np.array([level_name(s, thresholds) for s in scores])
    return {
        "n": int(len(y)),
        "positive_rate": float(y.mean()),
        "roc_auc": float(roc_auc_score(y, scores)),
        "pr_auc": float(average_precision_score(y, scores)),
        "brier": float(brier_score_loss(y, scores)),
        "brier_uncalibrated": float(brier_score_loss(y, uncalibrated_scores)),
        "threshold": threshold,
        "report": classification_report(
            y,
            predicted,
            labels=[0, 1],
            target_names=["no_incident", "incident"],
            output_dict=True,
            zero_division=0,
        ),
        "confusion_matrix": confusion_matrix(y, predicted, labels=[0, 1]).tolist(),
        "baseline_cell_rate": {
            "roc_auc": float(roc_auc_score(y, baseline_scores)),
            "pr_auc": float(average_precision_score(y, baseline_scores)),
            "brier": float(brier_score_loss(y, baseline_scores)),
        },
        "levels": [
            {
                "level": level,
                "n": int((levels == level).sum()),
                "observed_rate": float(y[levels == level].mean())
                if (levels == level).any()
                else None,
            }
            for level in LEVELS
        ],
    }


def train(config: RiskTrainConfig, artefact_root: Path, data_dir: Path,
          report_path: Path | None) -> dict:  # fmt: skip
    cells = grid_cells(config.cell_size_m)
    weather, weather_source = load_weather(
        config.start, config.n_days, data_dir.parent / "raw", config.weather_source
    )
    incidents = generate_incidents(cells, config.start, config.n_days, weather, config.seed)
    incidents_csv = data_dir / f"incidents_jaipur_{config.cell_size_m}m.csv"
    write_csv(incidents, incidents_csv)
    labels = label_matrix(incidents, cells, config.start, config.n_days)
    train_end = int(config.n_days * TRAIN_FRACTION)
    validation_end = int(config.n_days * (TRAIN_FRACTION + VALIDATION_FRACTION))
    # Each cell's incident rate in the TRAINING period only (no look at later data).
    past_rates = labels[:, :train_end, :].mean(axis=(1, 2))
    x, y, day_index, cell_index = build_dataset(
        cells, config.start, config.n_days, weather, labels, past_rates
    )
    is_train = day_index < train_end
    is_validation = (day_index >= train_end) & (day_index < validation_end)
    is_test = day_index >= validation_end

    # Stage 1: choose the algorithm with blocked spatial CV (place + time features).
    models = candidates(config)
    blocks = spatial_blocks(cells, config.block_cells)
    place_time = columns(PLACE_TIME_FEATURES)
    cv_table = cross_validate(
        models,
        x[is_train][:, place_time],
        y[is_train],
        blocks[cell_index[is_train]],
        config.cv_folds,
    )
    chosen = choose(cv_table, list(models))

    # Stage 2: keep the cell's past rate only if it helps on the validation period.
    stage2 = []
    for names in (PLACE_TIME_FEATURES, FEATURE_NAMES):
        cols = columns(names)
        candidate = clone(models[chosen]).fit(x[is_train][:, cols], y[is_train])
        scores = candidate.predict_proba(x[is_validation][:, cols])[:, 1]
        stage2.append(
            {
                "features": "with past rate" if "cell_past_rate" in names else "place + time",
                "names": names,
                "validation_pr_auc": float(average_precision_score(y[is_validation], scores)),
                "model": candidate,
            }
        )
    with_history = stage2[1]["validation_pr_auc"] >= stage2[0]["validation_pr_auc"] + MIN_GAIN
    selected = stage2[1] if with_history else stage2[0]
    feature_names, fitted = selected["names"], selected["model"]
    cols = columns(feature_names)

    calibrated = CalibratedClassifierCV(FrozenEstimator(fitted), method="isotonic").fit(
        x[is_validation][:, cols], y[is_validation]
    )
    threshold = best_f1_threshold(
        y[is_validation], calibrated.predict_proba(x[is_validation][:, cols])[:, 1]
    )

    # Baseline: each cell's incident rate in the training period (no time information).
    cell_rate = np.bincount(cell_index[is_train], weights=y[is_train], minlength=len(cells))
    cell_rate /= np.bincount(cell_index[is_train], minlength=len(cells))
    test_metrics = evaluate(
        calibrated.predict_proba(x[is_test][:, cols])[:, 1],
        y[is_test],
        threshold,
        config.level_thresholds,
        cell_rate[cell_index[is_test]],
        fitted.predict_proba(x[is_test][:, cols])[:, 1],
    )

    params = {
        **{k: (str(v) if isinstance(v, date) else v) for k, v in asdict(config).items()},
        "chosen_model": chosen,
        "feature_names": feature_names,
        "weather_source_used": weather_source,
        "sklearn_version": sklearn.__version__,
    }
    digest = hashlib.sha256(
        incidents_csv.read_bytes() + json.dumps(params, sort_keys=True).encode()
    )
    version = f"riskmodel-v1-{digest.hexdigest()[:10]}"
    period = {
        "start": str(config.start),
        "train_until": str(config.start + timedelta(days=train_end - 1)),
        "validation_until": str(config.start + timedelta(days=validation_end - 1)),
        "test_until": str(config.start + timedelta(days=config.n_days - 1)),
    }
    out_dir = artefact_root / version
    out_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(calibrated, out_dir / "model.joblib")
    metadata = {
        "model_version": version,
        "model_type": chosen,
        "feature_names": feature_names,
        # Training-period incident rate per cell (looked up by cell name in the app).
        "cell_past_rates": {
            cell.name(config.cell_size_m): float(rate)
            for cell, rate in zip(cells, past_rates, strict=True)
        },
        "default_past_rate": float(past_rates.mean()),
        "cell_size_m": config.cell_size_m,
        "time_bins": TIME_BINS,
        "level_thresholds": list(config.level_thresholds),
        "decision_threshold": threshold,
        "weather_source": weather_source,
        "synthetic_training_data": True,
        "period": period,
        "params": params,
    }
    (out_dir / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    summary = {
        "n_cells": len(cells),
        "n_incidents": len(incidents),
        "incidents_by_category": {c: sum(i.category == c for i in incidents) for c in CATEGORIES},
        "positive_rate": {
            "train": float(y[is_train].mean()),
            "validation": float(y[is_validation].mean()),
            "test": float(y[is_test].mean()),
        },
    }
    result = {
        "version": version,
        "chosen": chosen,
        "cv": cv_table,
        "stage2": [{k: v for k, v in row.items() if k != "model"} for row in stage2],
        "uses_past_rate": with_history,
        "summary": summary,
        "period": period,
        "test": test_metrics,
        "importances": importances(fitted, chosen, feature_names),
        "weather_source": weather_source,
    }
    (out_dir / "metrics.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    (artefact_root / "LATEST").write_text(version, encoding="utf-8")
    if report_path is not None:
        write_report(report_path, config, result)
    return result


def _fmt(value) -> str:
    return "n/a" if value is None else f"{value:.3f}"


def write_report(path: Path, config: RiskTrainConfig, r: dict) -> None:
    t = r["test"]
    rep = t["report"]
    lines = [
        "# Risk model report (SYNTHETIC data)",
        "",
        "> Trained and evaluated on **synthetic** incidents (ml/incident_data.py). The score is a",
        "> **relative decision-support estimate** of the chance that at least one tourist incident",
        "> is reported in a ~1 km cell during a 6-hour period. It is **not** a prediction that a",
        "> crime will occur, and these numbers say **nothing** about real-world accuracy.",
        "> Regenerate with `python -m ml.train_risk_model`.",
        "",
        f"- Model version: `{r['version']}`; chosen model: **{r['chosen']}**, isotonic-calibrated",
        f"- Grid: {r['summary']['n_cells']} cells of {config.cell_size_m} m; 4 bins of 6 h a day",
        f"- Period: {r['period']['start']} to {r['period']['test_until']} "
        f"(train to {r['period']['train_until']}, validation to "
        f"{r['period']['validation_until']}, test after)",
        f"- Weather source: {r['weather_source']}",
        f"- Synthetic incidents: {r['summary']['n_incidents']}; seed {config.seed}",
        "- Cell-bins with at least one incident: "
        + ", ".join(f"{k} {v:.3f}" for k, v in r["summary"]["positive_rate"].items()),
        "",
        "## Model choice (blocked spatial CV on the training period)",
        "",
        "| Model | PR-AUC mean | PR-AUC std | ROC-AUC mean |",
        "|---|---|---|---|",
        *[
            f"| {row['model']} | {row['pr_auc_mean']:.3f} | {row['pr_auc_std']:.3f} | "
            f"{row['roc_auc_mean']:.3f} |"
            for row in r["cv"]
        ],
        "",
        "Rule: the simplest model (logistic regression before random forest) whose mean PR-AUC "
        "is within one standard deviation of the best. Features in this stage: place + time.",
        "",
        "## History feature (validation period)",
        "",
        "| Features | Validation PR-AUC |",
        "|---|---|",
        *[f"| {row['features']} | {row['validation_pr_auc']:.3f} |" for row in r["stage2"]],
        "",
        f"The cell's past rate is kept only if it adds at least {MIN_GAIN} validation PR-AUC "
        f"(assumption). Result: **{'kept' if r['uses_past_rate'] else 'not kept'}**.",
        "",
        "## Test period results (see the development history below)",
        "",
        "| Metric | Model (calibrated) | Baseline: cell's historical rate |",
        "|---|---|---|",
        f"| ROC-AUC | {t['roc_auc']:.3f} | {t['baseline_cell_rate']['roc_auc']:.3f} |",
        f"| PR-AUC | {t['pr_auc']:.3f} | {t['baseline_cell_rate']['pr_auc']:.3f} |",
        f"| Brier score (lower is better) | {t['brier']:.4f} | "
        f"{t['baseline_cell_rate']['brier']:.4f} |",
        "",
        f"- Brier score of the same model BEFORE calibration: {t['brier_uncalibrated']:.4f} "
        "(class weights make raw scores too high; calibration fixes the scale).",
        f"- Share of test cell-bins with an incident: {t['positive_rate']:.3f}",
        "",
        f"### At the decision threshold {t['threshold']:.3f} (max F1 on the validation period)",
        "",
        "| Class | Precision | Recall | F1 | Support |",
        "|---|---|---|---|---|",
        *[
            f"| {name} | {rep[name]['precision']:.3f} | {rep[name]['recall']:.3f} | "
            f"{rep[name]['f1-score']:.3f} | {int(rep[name]['support'])} |"
            for name in ["no_incident", "incident"]
        ],
        f"| macro average | {rep['macro avg']['precision']:.3f} | "
        f"{rep['macro avg']['recall']:.3f} | {rep['macro avg']['f1-score']:.3f} | |",
        "",
        "Confusion matrix (rows = true, columns = predicted):",
        "",
        "| | predicted no incident | predicted incident |",
        "|---|---|---|",
        f"| true no incident | {t['confusion_matrix'][0][0]} | {t['confusion_matrix'][0][1]} |",
        f"| true incident | {t['confusion_matrix'][1][0]} | {t['confusion_matrix'][1][1]} |",
        "",
        "### Risk levels on the test period (thresholds "
        + " / ".join(str(v) for v in config.level_thresholds)
        + ", initial assumptions)",
        "",
        "| Level | Cell-bins | Observed share with an incident |",
        "|---|---|---|",
        *[f"| {row['level']} | {row['n']} | {_fmt(row['observed_rate'])} |" for row in t["levels"]],
        "",
        "If the model is useful, the observed share should rise from LOW to CRITICAL.",
        "",
        "## What the model relies on",
        "",
        "| Feature | Importance |",
        "|---|---|",
        *[f"| {name} | {value:.3f} |" for name, value in r["importances"]],
        "",
        "(Random forest: impurity importance; logistic regression: size of standardised "
        "coefficient.)",
        "",
        "## Development history",
        "",
        *[f"- {line}" for line in DEVELOPMENT_HISTORY],
        "",
        "## Known limitations",
        "",
        "- The data is synthetic: the generator's hand-chosen hotspots and effects define what "
        "there is to learn. Three hotspots are hidden from the features on purpose.",
        "- The only history used is each cell's FIXED training-period rate; there are no "
        "recent-incident features (the live database is almost empty). A real system would "
        "update the rates as new reports arrive.",
        "- The validation period is used for the history-feature decision, calibration and the "
        "threshold.",
        "- The test period (late summer / monsoon) differs from most of the training period "
        "(tourist season), which is realistic but lowers the scores.",
        "- SMOTE was not used (class weights instead); XGBoost was not evaluated.",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    config = RiskTrainConfig()
    print("Training the risk model on SYNTHETIC data (takes about a minute)...")
    result = train(
        config,
        artefact_root=REPO_ROOT / "ml" / "artefacts" / "risk_model",
        data_dir=REPO_ROOT / "ml" / "data" / "synthetic",
        report_path=REPO_ROOT / "ml" / "reports" / "risk_model.md",
    )
    t = result["test"]
    print(f"Model {result['version']} ({result['chosen']}), weather: {result['weather_source']}")
    print(
        f"Test: ROC-AUC {t['roc_auc']:.3f}, PR-AUC {t['pr_auc']:.3f}, Brier {t['brier']:.4f}; "
        f"baseline PR-AUC {t['baseline_cell_rate']['pr_auc']:.3f}"
    )
    print("Report: ml/reports/risk_model.md")


if __name__ == "__main__":
    sys.exit(main())
