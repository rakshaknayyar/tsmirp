# ML workspace

Everything here is reproducible with fixed seeds. All data is **synthetic** (or open data
used only to test code), and every result on it is labelled synthetic.

## Text classifier (Phase 6)

Run from the repository root:

```
python -m ml.train_text_classifier
```

This one command:
1. generates the synthetic incident texts (`ml/text_data.py`: English, Hindi, romanised
   Hindi, from hand-written templates) into `ml/data/synthetic/incident_texts.csv`;
2. trains TF-IDF + logistic regression on the English rows, choosing the features and the
   regularisation strength by grouped cross-validation (simplest model within one standard
   deviation of the best);
3. calibrates the probabilities and evaluates once on **unseen templates**;
4. saves the model under `ml/artefacts/text_classifier/<version>/` (git-ignored) with
   `LATEST` pointing to it - the API loads this;
5. writes the report `ml/reports/text_classifier.md` (committed).

The same seed and data always give the same version name and the same numbers.

**What the numbers mean:** they show that the pipeline works on clean, template-generated
text. They do **not** show real-world accuracy; real reports are messier.

## Risk model (Phase 7)

Run from the repository root (about a minute):

```
python -m ml.train_risk_model
```

1. daily weather for the period from the Open-Meteo archive (cached in `ml/data/raw/`;
   an approximate monthly table is used if it cannot be downloaded - the report says which);
2. one year of synthetic incidents (`ml/incident_data.py`) turned into labels per ~1 km grid
   cell and 6-hour bin;
3. features from `backend/app/ml/risk_features.py` - the same code the API uses;
4. chronological split, blocked spatial CV, a validation-based check of the history feature,
   isotonic calibration, threshold tuning, one evaluation on the test period;
5. artefacts under `ml/artefacts/risk_model/<version>/` (git-ignored, `LATEST` points to the
   version) and the report `ml/reports/risk_model.md` (committed).

## Still to come
- Phase 8: Hindi / romanised Hindi via a translation step, evaluated separately.
