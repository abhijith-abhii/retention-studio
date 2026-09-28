# Model evaluation

Selected: **Calibrated logistic regression**. Version: `model-b9d8a41f7b25`.

## Protocol

Seed 42; stratified 60/20/20 split: 4,225 training, 1,409 validation, 1,409 holdout. IDs are disjoint. Median numeric imputation, standardization, most-frequent categorical imputation, and one-hot encoding are fit inside training folds. Models are a prior baseline, balanced logistic regression, and a balanced random forest. Both learned candidates use 3-fold sigmoid calibration inside training. No oversampling occurs before splitting.

Highest validation average precision; prefer calibrated logistic regression within 0.015 of best. No refit on validation or holdout occurs after selection. Feature permutation explanations use validation only. The holdout is evaluated after model, calibration approach, and threshold are fixed. Re-running `train` deliberately repeats this fixed protocol; the holdout should not be used for iterative manual tuning.

| Candidate | Validation average precision | ROC-AUC | Brier |
|---|---:|---:|---:|
| Prior baseline | 0.2654 | 0.5000 | 0.1950 |
| Calibrated logistic regression | 0.6425 | 0.8361 | 0.1382 |
| Calibrated random forest | 0.6398 | 0.8391 | 0.1369 |

## Final holdout

| Metric | Result |
|---|---:|
| ROC-AUC | 0.8414 |
| Average precision (reported as PR-AUC) | 0.6346 |
| Precision | 0.7386 |
| Recall | 0.3021 |
| F1 | 0.4288 |
| Brier | 0.1384 |
| Precision among highest 141 scores | 0.7518 |
| Lift among highest 141 scores | 2.8322 |
| Fixed evaluation threshold | 0.637434 |

Confusion matrix, rows = observed [No, Yes], columns = predicted [No, Yes]: `[[995, 40], [261, 113]]`.

200 seeded paired bootstrap samples give approximate 95% intervals of 0.817–0.863 for ROC-AUC and 0.580–0.686 for average precision. They represent test-sample uncertainty conditional on this fitted model, not training or deployment uncertainty.

## Why these metrics and this threshold?

Accuracy can hide missed churners when most customers do not churn. Average precision evaluates minority-class retrieval; ROC-AUC summarizes ranking; precision measures review yield; recall measures missed churners; F1 summarizes their tradeoff. Lift compares precision at capacity with the holdout churn prevalence. Brier and the reliability curve check calibration.

The planning assumption is 100 weekly review slots out of 1,000 planned accounts (10.0%). This denominator is fixed in configuration **before** examining holdout outcomes. The corresponding top validation score cutoff becomes the evaluation threshold. The holdout flagged 153 records because sample distribution and ties differ. Top-k ranking uses stable row order for ties.

The actual pipeline uses a strict global UTC-week task capacity, eligibility filters, minimum score, then descending score with customer ID tie-breaking. Its run-specific cutoff is saved in execution history. This is separate from the evaluation threshold. Risk-band boundaries (0.35 / 0.65 by default) are business labels, not intervention thresholds.

## Calibration, leakage, and explanations

The saved reliability curve compares mean scores and observed churn fractions across eight quantile bins of the final holdout. Sigmoid calibration reduces distortion from class weighting, but calibration on an undated fictional snapshot cannot validate a future-event probability. UI scores are displayed on a 0–1 scale as historical-label estimates.

The input contract and ColumnTransformer allowlist exclude customer ID, Active, Churn, churn reason/score/value, status, CLTV, and arbitrary extra columns. Demographic columns remain in the raw source for provenance but are excluded from the model and rules. Tests verify target/ID changes cannot change predictions and reject target columns in scoring files. Pre-outcome availability cannot be verified; contemporaneous features remain a limitation even without explicit target leakage.

Permutation importance reports validation average-precision decline when each feature is shuffled (5 repeats). Correlated tenure, totals, and contract fields can share importance. Customer cards show observed fields supporting rule selection; these are deliberately labeled **playbook signals**, not local model explanations or causal effects.

Only active holdout accounts are used in the demonstration queue. Their labels were used to construct an active demo pool after evaluation. This is not an independent prospective scoring cohort, and no queue churn prevalence or retention effectiveness is claimed.

Artifacts include the complete calibrated preprocessing pipeline, evaluation JSON, split ID manifest, data hash, seed, dependency versions, and source configuration. Only load trusted locally generated joblib files.
