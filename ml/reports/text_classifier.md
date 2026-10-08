# Text classifier report (SYNTHETIC data)

> All numbers below are measured on **synthetic, template-generated** English text.
> They show that the pipeline works; they do **not** show real-world accuracy.
> Regenerate with `python -m ml.train_text_classifier`.

- Model version: `textclf-v1-7f49156483`
- Model: TF-IDF (word n-grams) + logistic regression, C = 0.1, sigmoid-calibrated probabilities
- Languages trained: en
- Seed: 42; scikit-learn 1.9.1
- Train rows: 2064; test rows: 636 (test = unseen templates)

## Choosing the model (5-fold grouped CV on training templates, macro-F1)

| Features | C | mean | std |
|---|---|---|---|
| word | 0.1 | 0.653 | 0.067 |
| word | 0.3 | 0.661 | 0.068 |
| word | 1.0 | 0.666 | 0.071 |
| word | 3.0 | 0.667 | 0.072 |
| word | 10.0 | 0.666 | 0.070 |
| word+char | 0.1 | 0.708 | 0.050 |
| word+char | 0.3 | 0.703 | 0.064 |
| word+char | 1.0 | 0.707 | 0.062 |
| word+char | 3.0 | 0.710 | 0.062 |
| word+char | 10.0 | 0.709 | 0.061 |

Rule: the simplest model within one standard deviation of the best mean (word before word+char, then smaller C).

## Test results (unseen templates)

| Metric | Model | Most-frequent baseline |
|---|---|---|
| Accuracy | 0.719 | 0.094 |
| Macro precision | 0.711 | - |
| Macro recall | 0.705 | - |
| Macro F1 | 0.696 | 0.019 |

### Calibration (are the confidence values honest?)

- Mean confidence: 0.571 vs accuracy 0.719 - the model is UNDER-confident (cautious): it is right more often than its confidence suggests, so it flags more reports for review than strictly needed.
- Multi-class Brier score: 0.473 (0 = perfect; lower is better)

### Per class

| Category | Precision | Recall | F1 | Test rows |
|---|---|---|---|---|
| theft | 0.823 | 0.952 | 0.883 | 83 |
| harassment | 0.733 | 1.000 | 0.846 | 74 |
| medical_emergency | 0.761 | 0.778 | 0.769 | 90 |
| accident | 0.853 | 0.446 | 0.586 | 65 |
| lost_person | 0.746 | 0.691 | 0.718 | 68 |
| suspicious_activity | 0.618 | 0.493 | 0.548 | 69 |
| natural_disaster | 0.573 | 0.717 | 0.637 | 60 |
| fire | 0.985 | 1.000 | 0.992 | 64 |
| other | 0.309 | 0.270 | 0.288 | 63 |

### Confusion matrix (rows = true, columns = predicted)

| true \ predicted | theft | harassment | medical_emergency | accident | lost_person | suspicious_activity | natural_disaster | fire | other |
|---|---|---|---|---|---|---|---|---|---|
| theft | 79 | 0 | 0 | 4 | 0 | 0 | 0 | 0 | 0 |
| harassment | 0 | 74 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| medical_emergency | 0 | 0 | 70 | 0 | 1 | 3 | 1 | 0 | 15 |
| accident | 0 | 0 | 1 | 29 | 0 | 16 | 18 | 0 | 1 |
| lost_person | 17 | 0 | 3 | 1 | 47 | 0 | 0 | 0 | 0 |
| suspicious_activity | 0 | 0 | 0 | 0 | 0 | 34 | 13 | 0 | 22 |
| natural_disaster | 0 | 0 | 1 | 0 | 15 | 0 | 43 | 1 | 0 |
| fire | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 64 | 0 |
| other | 0 | 27 | 17 | 0 | 0 | 2 | 0 | 0 | 17 |

### Human-review flag (confidence < 0.5)

- Share of test rows flagged: 0.374
- Accuracy on rows NOT flagged: 0.807
- Accuracy on flagged rows: 0.571

The threshold is an initial assumption; the right value is to be determined experimentally on real, labelled reports.

## Sanity examples

| Text | Predicted | Confidence |
|---|---|---|
| My phone was stolen near the market | theft | 0.722 |
| A man keeps following me and will not go away | harassment | 0.786 |
| There is smoke everywhere, the hotel kitchen is burning | fire | 0.791 |

## Development history

- First run (10 English templates per category, word features only): test macro-F1 0.444, and every test row fell below the review threshold. The test set was therefore looked at once during development.
- Change made because of it: about 8 more templates per category (more varied wording) and character n-grams offered as a candidate feature set. Feature set and C are chosen by cross-validation on the training data only; the test split was not tuned.
- Second run (uncalibrated): test macro-F1 0.657, but every test row was still below the review threshold, because a strongly regularised model gives low, squashed probabilities. Change: probability calibration (sigmoid) fitted on grouped training folds. Calibration changes the confidence values, not the model choice.

## Known limitations

- Synthetic templates are much cleaner than real reports, so these scores are optimistic.
- English only here; Hindi and romanised Hindi are handled in Phase 8 (translation).
- The model sees words, not meaning: unusual wording can be misclassified with high confidence. Operators can always override the category.
