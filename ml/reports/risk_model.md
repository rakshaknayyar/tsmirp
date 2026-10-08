# Risk model report (SYNTHETIC data)

> Trained and evaluated on **synthetic** incidents (ml/incident_data.py). The score is a
> **relative decision-support estimate** of the chance that at least one tourist incident
> is reported in a ~1 km cell during a 6-hour period. It is **not** a prediction that a
> crime will occur, and these numbers say **nothing** about real-world accuracy.
> Regenerate with `python -m ml.train_risk_model`.

- Model version: `riskmodel-v1-ed5d5ed06e`; chosen model: **logistic_regression**, isotonic-calibrated
- Grid: 460 cells of 1000 m; 4 bins of 6 h a day
- Period: 2024-10-01 to 2025-09-30 (train to 2025-06-12, validation to 2025-08-06, test after)
- Weather source: open-meteo-archive
- Synthetic incidents: 13130; seed 42
- Cell-bins with at least one incident: train 0.018, validation 0.011, test 0.012

## Model choice (blocked spatial CV on the training period)

| Model | PR-AUC mean | PR-AUC std | ROC-AUC mean |
|---|---|---|---|
| logistic_regression | 0.120 | 0.152 | 0.712 |
| random_forest | 0.079 | 0.083 | 0.703 |

Rule: the simplest model (logistic regression before random forest) whose mean PR-AUC is within one standard deviation of the best. Features in this stage: place + time.

## History feature (validation period)

| Features | Validation PR-AUC |
|---|---|
| place + time | 0.157 |
| with past rate | 0.246 |

The cell's past rate is kept only if it adds at least 0.01 validation PR-AUC (assumption). Result: **kept**.

## Test period results (see the development history below)

| Metric | Model (calibrated) | Baseline: cell's historical rate |
|---|---|---|
| ROC-AUC | 0.889 | 0.867 |
| PR-AUC | 0.266 | 0.234 |
| Brier score (lower is better) | 0.0101 | 0.0107 |

- Brier score of the same model BEFORE calibration: 0.0556 (class weights make raw scores too high; calibration fixes the scale).
- Share of test cell-bins with an incident: 0.012

### At the decision threshold 0.187 (max F1 on the validation period)

| Class | Precision | Recall | F1 | Support |
|---|---|---|---|---|
| no_incident | 0.993 | 0.988 | 0.990 | 99947 |
| incident | 0.312 | 0.428 | 0.361 | 1253 |
| macro average | 0.652 | 0.708 | 0.676 | |

Confusion matrix (rows = true, columns = predicted):

| | predicted no incident | predicted incident |
|---|---|---|
| true no incident | 98764 | 1183 |
| true incident | 717 | 536 |

### Risk levels on the test period (thresholds 0.25 / 0.5 / 0.75, initial assumptions)

| Level | Cell-bins | Observed share with an incident |
|---|---|---|
| LOW | 99915 | 0.008 |
| MODERATE | 1199 | 0.315 |
| HIGH | 78 | 0.692 |
| CRITICAL | 8 | 0.750 |

If the model is useful, the observed share should rise from LOW to CRITICAL.

## What the model relies on

| Feature | Importance |
|---|---|
| cell_past_rate | 0.939 |
| time_bin | 0.440 |
| dist_landmark_km | 0.335 |
| tourist_season | 0.260 |
| rain_mm | 0.087 |
| is_weekend | 0.072 |
| dist_centre_km | 0.035 |
| landmarks_within_1km | 0.033 |
| month_cos | 0.014 |
| temp_max_c | 0.012 |
| month_sin | 0.007 |

(Random forest: impurity importance; logistic regression: size of standardised coefficient.)

## Development history

- First run (place + time features only, logistic regression chosen): test PR-AUC 0.185 vs 0.234 for the 'cell's historical rate' baseline, i.e. worse than the baseline, because three synthetic hotspots are hidden from the landmark features. The test period was therefore looked at once during development.
- Change made because of it: the cell's training-period incident rate was offered as an extra feature, kept only if it improves the VALIDATION PR-AUC (stage 2).

## Known limitations

- The data is synthetic: the generator's hand-chosen hotspots and effects define what there is to learn. Three hotspots are hidden from the features on purpose.
- The only history used is each cell's FIXED training-period rate; there are no recent-incident features (the live database is almost empty). A real system would update the rates as new reports arrive.
- The validation period is used for the history-feature decision, calibration and the threshold.
- The test period (late summer / monsoon) differs from most of the training period (tourist season), which is realistic but lowers the scores.
- SMOTE was not used (class weights instead); XGBoost was not evaluated.
