"""Generate interview-ready findings from actual saved results, not hardcoded claims."""
import json
from .paths import ROOT

def write_reports(root=ROOT):
    a=json.loads((root/'reports/analysis.json').read_text())
    version=json.loads((root/'artifacts/current.json').read_text())['version']
    e=json.loads((root/'artifacts'/version/'evaluation.json').read_text())
    h=e['holdout']
    lines=['# Customer churn analysis','',
        '## Business question and scope','',
        'A fictional subscription telecom team needs to understand which accounts resemble historical churners, decide which active accounts to review, and track its work. This project supports prioritization and operational learning; it does not demonstrate that outreach prevents churn.','',
        '## Observed facts in the sample','',
        f"- {a['customers']:,} unique customer records; {a['churned']:,} labeled Churn = Yes ({a['churn_rate']:.2%}); {a['active']:,} labeled No.",
        f"- Active reference accounts have {a['active_monthly_charges']:,.2f} in listed monthly charges. This sum is not realized revenue, MRR, expected loss, or recoverable value.",
        f"- {a['missing_total_charges']} total-charge values are blank and occur at zero tenure. They remain missing in cleaned data; model preprocessing imputes using training-fold medians.",'',
        'Churn is defined as the supplied binary Yes label. No is treated as active for the simulation. The CSV has no observation dates or dated churn events, so the report calls this an observed snapshot share, not a measured monthly churn rate. The data describes a fictional company. All numbers are properties of the sample, not a real business.','',
        '## Segment evidence','', '| Dimension | Segment | Churn / customers | Share | 95% Wilson interval |','|---|---|---:|---:|---:|']
    for dimension,rows in a['segments'].items():
        for r in rows:
            lines.append(f"| {dimension} | {r['segment']} | {r['churned']:,} / {r['customers']:,} | {r['rate']:.1%} | {r['ci_low']:.1%}–{r['ci_high']:.1%} |")
    lines += ['', '## Actions worth testing','',
        '1. **Early-tenure onboarding:** the shortest-tenure segment has the highest observed churn share. Offer setup assistance to eligible early-tenure accounts, then measure results with a control group.',
        '2. **Plan-fit conversations:** month-to-month customers have a much higher churn share than annual-contract customers. Customer selection, tenure, pricing, and contract terms may confound this comparison; moving customers to longer contracts is not proven to prevent churn.',
        '3. **Billing clarity:** electronic-check payment is associated with churn. For eligible higher-charge accounts, offer a bill walkthrough. Do not infer failed payments, financial distress, or dissatisfaction.',
        '4. **Product education:** the technical-support field is a subscribed add-on, not evidence of support tickets. Explain available help without inventing incidents or service failures.','',
        '## Data and interpretation limits','',
        '- No behavioral usage, support incidents, contact permission, channel details, margin, discounts, or dated outcomes are provided.',
        '- Segment shares use all observed customers in that segment as the denominator. Wilson intervals do not account for selection bias, confounding, multiple comparisons, or fictional data generation.',
        '- Segments under 50 customers are flagged by the application. The displayed reference segments exceed this minimum, but that does not establish external validity.',
        '- Demographics are excluded from scoring and recommendations. Proxy bias is still possible; no claim of fairness is made.',
        '- Monetary values retain source numeric units. The dashboard uses a dollar sign as a presentation assumption; currency is not independently verified in the CSV.',
        '- TotalCharges is a cumulative field. It is not expected to equal current MonthlyCharges × tenure because historical prices and partial periods are unavailable. The validator rejects negative/nonfinite values, fractional tenure, positive totals at zero tenure, and inconsistent service categories; it does not impose that unsupported equality.','',
        '## Source','',
        '[IBM source repository](https://github.com/IBM/telco-customer-churn-on-icp4d), pinned in `data/raw/source.json`. The original CSV is redistributed unchanged with the repository’s Apache-2.0 license and attribution. See DATA.md for provenance and permissions.']
    (root/'reports/ANALYSIS.md').write_text('\n'.join(lines)+'\n')
    candidates='\n'.join(f"| {name} | {m['pr_auc']:.4f} | {m['roc_auc']:.4f} | {m['brier']:.4f} |" for name,m in e['validation'].items())
    model=f'''# Model evaluation

Selected: **{e['selected']}**. Version: `{e['version']}`.

## Protocol

Seed {e['seed']}; stratified 60/20/20 split: {e['split']['train']:,} training, {e['split']['validation']:,} validation, {e['split']['holdout']:,} holdout. IDs are disjoint. Median numeric imputation, standardization, most-frequent categorical imputation, and one-hot encoding are fit inside training folds. Models are a prior baseline, balanced logistic regression, and a balanced random forest. Both learned candidates use 3-fold sigmoid calibration inside training. No oversampling occurs before splitting.

{e['selection_rule']} No refit on validation or holdout occurs after selection. Feature permutation explanations use validation only. The holdout is evaluated after model, calibration approach, and threshold are fixed. Re-running `train` deliberately repeats this fixed protocol; the holdout should not be used for iterative manual tuning.

| Candidate | Validation average precision | ROC-AUC | Brier |
|---|---:|---:|---:|
{candidates}

## Final holdout

| Metric | Result |
|---|---:|
| ROC-AUC | {h['roc_auc']:.4f} |
| Average precision (reported as PR-AUC) | {h['pr_auc']:.4f} |
| Precision | {h['precision']:.4f} |
| Recall | {h['recall']:.4f} |
| F1 | {h['f1']:.4f} |
| Brier | {h['brier']:.4f} |
| Precision among highest {h['top_k']} scores | {h['precision_at_k']:.4f} |
| Lift among highest {h['top_k']} scores | {h['lift_at_k']:.4f} |
| Fixed evaluation threshold | {h['threshold']:.6f} |

Confusion matrix, rows = observed [No, Yes], columns = predicted [No, Yes]: `{h['confusion_matrix']}`.

200 seeded paired bootstrap samples give approximate 95% intervals of {e['bootstrap_95']['roc_auc'][0]:.3f}–{e['bootstrap_95']['roc_auc'][1]:.3f} for ROC-AUC and {e['bootstrap_95']['pr_auc'][0]:.3f}–{e['bootstrap_95']['pr_auc'][1]:.3f} for average precision. They represent test-sample uncertainty conditional on this fitted model, not training or deployment uncertainty.

## Why these metrics and this threshold?

Accuracy can hide missed churners when most customers do not churn. Average precision evaluates minority-class retrieval; ROC-AUC summarizes ranking; precision measures review yield; recall measures missed churners; F1 summarizes their tradeoff. Lift compares precision at capacity with the holdout churn prevalence. Brier and the reliability curve check calibration.

The planning assumption is {e['weekly_capacity_at_training']} weekly review slots out of {e['evaluation_pool_size']:,} planned accounts ({e['capacity_fraction']:.1%}). This denominator is fixed in configuration **before** examining holdout outcomes. The corresponding top validation score cutoff becomes the evaluation threshold. The holdout flagged {h['selected_count']} records because sample distribution and ties differ. Top-k ranking uses stable row order for ties.

The actual pipeline uses a strict global UTC-week task capacity, eligibility filters, minimum score, then descending score with customer ID tie-breaking. Its run-specific cutoff is saved in execution history. This is separate from the evaluation threshold. Risk-band boundaries (0.35 / 0.65 by default) are business labels, not intervention thresholds.

## Calibration, leakage, and explanations

The saved reliability curve compares mean scores and observed churn fractions across eight quantile bins of the final holdout. Sigmoid calibration reduces distortion from class weighting, but calibration on an undated fictional snapshot cannot validate a future-event probability. UI scores are displayed on a 0–1 scale as historical-label estimates.

The input contract and ColumnTransformer allowlist exclude customer ID, Active, Churn, churn reason/score/value, status, CLTV, and arbitrary extra columns. Demographic columns remain in the raw source for provenance but are excluded from the model and rules. Tests verify target/ID changes cannot change predictions and reject target columns in scoring files. Pre-outcome availability cannot be verified; contemporaneous features remain a limitation even without explicit target leakage.

Permutation importance reports validation average-precision decline when each feature is shuffled (5 repeats). Correlated tenure, totals, and contract fields can share importance. Customer cards show observed fields supporting rule selection; these are deliberately labeled **playbook signals**, not local model explanations or causal effects.

Only active holdout accounts are used in the demonstration queue. Their labels were used to construct an active demo pool after evaluation. This is not an independent prospective scoring cohort, and no queue churn prevalence or retention effectiveness is claimed.

Artifacts include the complete calibrated preprocessing pipeline, evaluation JSON, split ID manifest, data hash, seed, dependency versions, and source configuration. Only load trusted locally generated joblib files.
'''
    (root/'reports/MODEL_EVALUATION.md').write_text(model)
    resume=f'''# Resume bullets

- Built a Python and SQLite churn-analysis application with a seven-view interactive dashboard, strict validation of 7,043 fictional telecom records, and reproducible training and scoring workflows.
- Compared a prior baseline, calibrated logistic regression, and calibrated random forest using disjoint training, validation, and holdout splits; selected a model with {h['roc_auc']:.3f} holdout ROC-AUC and {h['pr_auc']:.3f} average precision.
- Implemented a configurable retention rules engine with weekly capacity, cooldowns, idempotent execution, audited status changes, CSV exports, and human-review outreach drafts; verified a 100-task simulation from 1,035 active held-out accounts.

These describe implemented work and sample-dataset results. Do not claim real revenue saved, reduced churn, a production deployment, or messages sent.
'''
    (root/'reports/RESUME_BULLETS.md').write_text(resume)
