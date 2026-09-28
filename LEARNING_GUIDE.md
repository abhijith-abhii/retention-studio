# Retention Studio — learning guide

## What it does

Prioritize reviewable churn retention work. The intended user is customer success analysts. Raw IBM sample → validated split/model pipeline → scoring and eligibility → transactional SQLite workflow → Flask dashboard.

## Run and demonstrate

Follow the README installation block, then: Bootstrap from raw sample data, start the dashboard, inspect model evaluation, score the active sample, assign a task and review its audit history. Repeat the same score input to verify idempotency.

## Important files

- `src/retention/model.py` — splits, fitting and evaluation.
- `src/retention/playbook.py` — eligibility and capacity.
- `src/retention/store.py` — transaction and audit layer.
- `config/playbook.yaml` — explicit policy assumptions.

## Three engineering decisions

1. Use disjoint train/validation/holdout partitions and fit preprocessing inside the model pipeline.
2. Eligibility, cooldown and weekly capacity are operational constraints applied after scoring.
3. SQLite transactions, idempotency keys and an audit trail protect repeated scoring runs and task changes.

## Five interview questions

1. **What does the retention queue represent?** A bounded list of customers to review under a configured outreach capacity. It operationalizes model scores but does not prove an intervention will prevent churn.

2. **Why calibrate churn probabilities?** Ranking and probability quality are different. Calibration makes probability estimates more interpretable for a capacity-limited review workflow, subject to the historical data assumptions.

3. **How is repeat outreach controlled?** The workflow records decisions in SQLite and applies cooldown rules. An audit history makes queue transitions and previous actions inspectable.

4. **What is the dataset limitation?** The telecom data is fictional and historical-label based. It is not a randomized intervention dataset, so the project cannot estimate causal retention uplift or real business savings.

5. **What evidence supports reproducibility?** A fresh bootstrap regenerated the project state and the 27-test suite passed. The repository preserves model evaluation, queue behavior and a working browser demonstration.

## Independent exercise

Add one eligibility rule to config/playbook.yaml and test its interaction with weekly capacity and cooldown.

Write down the expected behavior before editing. Add a meaningful regression check, run the existing suite, and describe what changed in your own words.

## Contribution and resume guidance

The implementation was developed with substantial AI assistance under Abhijith Viswanathan's direction. The verified contribution is the working artifact and the learning work actually completed, not invented employment or adoption.

Suggested factual bullet after personally validating the demo:

- Extended an AI-assisted churn review application with a capacity-limited action queue, cooldown rules and audit history; verified fresh bootstrap and 27 tests on fictional telecom data.

Use [VERIFICATION.md](VERIFICATION.md) to add only measured numbers. Do not claim production traffic, users, savings, upstream acceptance or cloud deployment without corresponding evidence.
