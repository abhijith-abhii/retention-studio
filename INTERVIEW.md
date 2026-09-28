# Interview preparation

## A clear project introduction

“I built a local churn-analysis and retention-workflow application on IBM's fictional telecom sample. I validated the source, compared calibrated classification models with a locked holdout, and converted model scores into capacity-limited review tasks. The engineering focus is reproducibility, safe reruns, persistence, and explainable rules. I explicitly separate historical association from future prediction and retention impact.”

## Why this architecture?

**Python for data and modeling.** pandas makes checks and aggregates readable; scikit-learn pipelines keep training transformations consistent at inference. I avoided paid APIs so the whole demo is reproducible locally.

**Flask plus a lightweight frontend.** A custom UI makes the customer explorer, queue editor, and audit dialog easy to use without a large frontend build system. The same-origin API reduces deployment pieces. Streamlit would have reduced UI authoring effort; Flask gives clearer request boundaries, input contracts, and persistence behavior to discuss in software interviews.

**SQLite for the local workflow.** ACID transactions, a unique partial index for open tasks, and a batch fingerprint solve real idempotency and consistency problems without an external database. Writes serialize with `BEGIN IMMEDIATE`; a busy timeout handles short contention. This is not a distributed queue or a high-throughput multi-tenant architecture.

## Explain the model honestly

**Why not accuracy?** Churn is a minority label. A majority classifier can be superficially accurate while finding no churners. Average precision evaluates positive-class ranking; precision at capacity maps to limited review slots; recall exposes how many positive labels the budget misses.

**How did you prevent leakage?** I split customer IDs before training, fit imputers/encoders/scalers inside training folds, calibrated within training, selected candidates on validation, and locked the threshold before final holdout evaluation. I use a feature allowlist and reject target or post-churn columns in scoring files. A static snapshot still cannot establish whether each field was available before churn—schema checks do not solve temporal leakage.

**Why calibrated logistic regression?** The selection rule prefers the simpler candidate when validation average precision is within 0.015 of the best candidate. Class weighting increases attention to churners, and sigmoid calibration addresses distorted scores. The held-out Brier score and reliability curve are checks, not evidence that real future probabilities are valid.

**Why random rather than time splitting?** The source contains no timestamps. A fabricated time axis would misrepresent the data. A production version needs dated snapshots and an explicit forecast horizon, with forward validation and customer grouping as necessary.

**What does an explanation mean?** Permutation importance measures validation performance sensitivity, not causal influence. The customer dialog's signals explain the playbook rule, not the exact model score. I did not call those signals SHAP values or claim that changing a contract would prevent churn.

**How did you choose the threshold?** I declared 100 weekly slots per 1,000 planned accounts before evaluating the holdout and used the validation top-decile cutoff. Actual operational eligibility and pool composition differ; the workflow therefore ranks eligible accounts and records each run's actual cutoff. Risk bands are separate configurable labels.

## Engineering tradeoffs to defend

**Idempotency vs. recurring action.** A successful input/model/config fingerprint prevents replay, even across weeks. New evidence must produce a refreshed input. Independent open-task uniqueness, cooldown, and weekly capacity prevent duplicate work across changed batches. This is intentionally conservative.

**Failure recovery.** Validation/scoring errors are recorded. Snapshot replacement and task insertion occur together in one transaction. Per-run files are written before commit; orphan failed-run artifacts are possible, but dashboard state stays on committed data. Abrupt termination can leave a Running entry; production work would add stale-run reconciliation and structured monitoring.

**Workflow persistence and stale edits.** Changes commit to SQLite and append audit records. The editor sends the last updated timestamp, so a second session cannot silently overwrite a newer task edit. Closed tasks stay closed; future eligible evidence can create a new task after cooldown.

**Security boundary.** It is a localhost-only single-user app with CSRF checks, trusted-host validation, HTML escaping, CSV formula protection, no credentials, and no external sending path. Production authentication, authorization, backups, migrations, access logs, and secret management are not implemented. Model deserialization is trusted-artifact-only.

**Rule safety.** The dataset lacks consent, support incidents, and contact addresses. I use onboarding, billing walkthrough, product education, and plan-fit review. A configured offer rule is disabled by default and only recommends a review. Service-recovery claims are not generated because the evidence is missing.

**Reproducibility vs. portability.** The source revision/hash, seed, split IDs, versioned artifact, and exact dependency lock capture the verified environment. A different Python/platform may need a compatible dependency resolution and retraining; byte-identical model binaries are not promised across platforms.

## How would you measure impact?

Use a fresh, dated production cohort. Randomly assign eligible customers to outreach or business-as-usual control before contact. Predefine churn event, follow-up horizon, assignment unit, exclusions, minimum detectable effect, sample size, and cost measurement. Compare churn rates by original assignment with confidence intervals (intention to treat), including nonresponders. Account for repeated customers, contamination, and multiple treatment arms. A post-contact retention observation alone cannot identify prevented churn.

## What would you build next?

1. A dated feature/label pipeline with point-in-time joins and forward validation.
2. Authenticated multi-user workflow and an explicitly authorized CRM/contact integration with consent and suppression checks.
3. Experiment assignment, outcome ingestion, calibration/drift monitoring, subgroup error analysis, and rollback/version governance.

Do not claim any of those future capabilities are already implemented. Use the generated resume bullets and evaluation summary for exact verified numbers.
