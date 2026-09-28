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

1. **What problem does this project solve, and what is its unit of work?** Explain prioritize reviewable churn retention work, identify customer success analysts as the audience, and trace one concrete example through the files above. Use the demonstration output rather than hypothetical impact.
2. **Why did you choose the first design decision?** Use disjoint train/validation/holdout partitions and fit preprocessing inside the model pipeline. Show the corresponding implementation and a test that would fail if that property were removed.
3. **How do you protect correctness when inputs or execution change?** Eligibility, cooldown and weekly capacity are operational constraints applied after scoring. Explain the relevant invalid-input or edge-case test and distinguish a checked property from an untested assumption.
4. **How do you make results inspectable and reproducible?** SQLite transactions, idempotency keys and an audit trail protect repeated scoring runs and task changes. Point to actual outputs and recorded commands. Explain why a successful example is weaker evidence than a tested boundary or independently reconciled total.
5. **What would you improve before real deployment or real-data use?** IBM data describe fictional undated telecom customers. Historical churn labels do not validate a future prediction horizon. Tasks and outcomes are simulation-only; no CRM messages, account changes or realized savings are claimed. Choose one limitation, describe the missing evidence, and propose a measurable acceptance check rather than promising production readiness.

## Independent exercise

Add one eligibility rule to config/playbook.yaml and test its interaction with weekly capacity and cooldown.

Write down the expected behavior before editing. Add a meaningful regression check, run the existing suite, and describe what changed in your own words.

## Contribution and resume guidance

The implementation was developed with substantial AI assistance under Abhijith Viswanathan's direction. The verified contribution is the working artifact and the learning work actually completed, not invented employment or adoption.

Suggested factual bullet after personally validating the demo:

- Implemented and validated prioritize reviewable churn retention work using pandas · scikit-learn · Flask, with calibrated models and documented correctness checks and limitations.

Use [VERIFICATION.md](VERIFICATION.md) to add only measured numbers. Do not claim production traffic, users, savings, upstream acceptance or cloud deployment without corresponding evidence.
