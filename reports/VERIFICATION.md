# Verification evidence

Verified locally on 2026-09-19 using Python 3.12, pandas 3.0.6, scikit-learn 1.9.1, Flask 3.1.3, and SQLite on macOS. Exact dependency versions are in `requirements-lock.txt`; model runtime metadata is in its evaluation artifact.

## Automated checks

`python -m pytest -q`: **27 passed** (final run: 2.04 seconds).

Coverage includes:

- 7,043 unique source rows, 1,869 churn labels, and the 11 blank total-charge values at zero tenure.
- Empty/unreadable input, missing/extra columns, duplicate/missing identifiers, invalid categories, invalid or nonfinite charges, fractional tenure, and inconsistent service fields.
- Missing-predictor imputation, target/ID exclusion, prediction consistency after reloading the saved pipeline, disjoint split IDs, and no training overlap in the demo scoring pool.
- Independent recomputation of the saved holdout metrics.
- Rule precedence, available-field outreach drafts, all risk bands, inactive/excluded/missing-signal eligibility, minimum score, open-task exclusion, and exact cooldown boundary.
- Repeat-run idempotency, weekly capacity across changed inputs, and simultaneous same-input execution (one success, one skip, 100 total tasks).
- Transaction rollback and last-good snapshot preservation after invalid inputs and after a simulated export disk failure.
- Persisted status/owner changes, optimistic edit conflict, terminal status restrictions, audit records, simulated observations, future-date rejection, and CSV formula protection.
- Local API, dashboard payload, CSRF mutation checks, trusted-host rejection, and current-status CSV export.

JavaScript syntax check passed. The final dashboard browser error/warning log was empty. The optional pinned download reproduced the exact 970,457-byte IBM CSV with SHA-256 `16320c9c1ec72448db59aa0a26a0b95401046bef5d02fd3aeb906448e3055e91`.

## End-to-end application checks

- `./start.sh` bootstrapped and served the app at **http://127.0.0.1:8766/**. A direct HTTP request returned 200.
- All seven dashboard views were inspected in the browser.
- Contract-to-tenure segment selection changed the chart, counts, and interval table.
- Searching `8161` returned exactly one customer; its detail dialog showed the expected billing rule, observed fields, review draft, versions, and audit trail.
- Changing `8161-QYMTT` to **Assigned** persisted through a page reload and server restart. Filtering the queue to Assigned returned that one task. The final local database intentionally contains this QA workflow change: 99 New and 1 Assigned task.
- Running the pipeline through the dashboard returned **Skipped**, created zero new tasks, and logged the run.
- Uploading a deliberately invalid one-column CSV produced a **Failed** run with a visible missing-column explanation. The 1,035-customer snapshot and 100-task queue remained intact. That intentional QA failure remains in pipeline history as evidence of error handling.
- Outcomes showed **0 records** and no impact claim. Setting the hypothetical improvement to zero changed hypothetical net value to **−$500**, the assumed outreach cost.
- Responsive layouts were visually inspected at 1280×900 and 390×844. Screenshot files show the actual running application, including the overview, model view, task editor, and mobile layout.

## Fresh-checkout reproducibility

A clean copy of only Git-eligible source files (excluding the environment, model binaries, derived CSVs, and operational database) successfully ran bootstrap. It regenerated the same model version and all holdout metrics exactly, then scored 1,035 accounts and created 100 tasks in a fresh database.

## Final verified results

| Item | Result |
|---|---:|
| Reference customers | 7,043 |
| Active held-out demonstration input | 1,035 |
| Retention tasks | 100 |
| Recorded outcomes | 0 |
| Holdout ROC-AUC | 0.8414 |
| Holdout average precision | 0.6346 |
| Precision among top 141 holdout scores | 0.7518 |
| Lift among top 141 holdout scores | 2.8322 |

## Deliberate limitations

This is local, simulation-only software. No production deployment, GitHub push, scheduler, real notifications, discounts, account changes, realized retention impact, or authenticated multi-user workflow was tested or claimed. No connected GitHub account/CLI was available. The app uses fictional static reference data and has no validated forecast horizon. Browser QA covered representative flows; it is not a full accessibility audit, load test, cross-browser matrix, or penetration test. The separate JSON metadata for earlier local model versions preserves the audit history; current evaluation results are identified by `artifacts/current.json`.
