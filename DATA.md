# Data source, contracts, and dictionary

## Provenance and permitted use

- Original publisher: IBM, `telco-customer-churn-on-icp4d` code pattern repository.
- [Repository](https://github.com/IBM/telco-customer-churn-on-icp4d), [original data](https://github.com/IBM/telco-customer-churn-on-icp4d/blob/master/data/Telco-Customer-Churn.csv), [repository license](https://github.com/IBM/telco-customer-churn-on-icp4d/blob/master/LICENSE).
- Pinned revision: `d5371f5d83a446ad5673cbcca3b814b926491f8a`. Exact URL, acquisition date, byte count, and SHA-256 are saved in `data/raw/source.json`.
- The IBM repository distributes the sample CSV under its Apache License 2.0; no separate data license is supplied in that directory. This project relies on that repository-level grant, preserves the original CSV unchanged, includes the complete license in `data/raw/LICENSE-IBM.txt`, and attributes IBM in `NOTICE`. Check the license and any applicable upstream terms before a different redistribution context.
- IBM describes its Telco sample as fictional. This is a public demonstration dataset, not a verified production customer population. No customer contact details or credentials are present. The repository was archived in 2024; retrieval date does not imply data freshness.

## Unit of observation and churn

One row per unique customer ID, with 7,043 records and 21 source columns. `Churn = Yes` is the supplied historical churn label. `No` is treated as active for this demonstration. The CSV includes no observation date, churn date, or history. Even if sample descriptions refer to a prior month, there is no calendar period or pre-event feature history to validate. Accordingly all analysis reports **snapshot churn share**, and the model has **no future prediction horizon**.

## Source dictionary

| Field | Type / valid values | Meaning and handling |
|---|---|---|
| customerID | unique string | Anonymous sample account key; required, never a model feature |
| gender | Female / Male | Source demographic category; excluded from model and rules |
| SeniorCitizen | 0 / 1 | Source indicator; excluded from model and rules |
| Partner | Yes / No | Source household field; excluded from model and rules |
| Dependents | Yes / No | Source household field; excluded from model and rules |
| tenure | nonnegative integer months | Months with company; ≤1,200 validation boundary; model feature and onboarding signal |
| PhoneService | Yes / No | Phone subscription; model feature |
| MultipleLines | Yes / No / No phone service | Multiple-line subscription; must agree with PhoneService |
| InternetService | DSL / Fiber optic / No | Internet service subscription, not usage intensity |
| OnlineSecurity | Yes / No / No internet service | Security add-on; must agree with InternetService |
| OnlineBackup | Yes / No / No internet service | Backup add-on; same consistency rule |
| DeviceProtection | Yes / No / No internet service | Protection add-on; same consistency rule |
| TechSupport | Yes / No / No internet service | Technical-support add-on; not support tickets or quality |
| StreamingTV | Yes / No / No internet service | Streaming subscription; not observed viewing activity |
| StreamingMovies | Yes / No / No internet service | Streaming subscription; not observed viewing activity |
| Contract | Month-to-month / One year / Two year | Current term; model and plan-fit signal |
| PaperlessBilling | Yes / No | Billing format; model feature |
| PaymentMethod | Electronic check / Mailed check / Bank transfer (automatic) / Credit card (automatic) | Recorded method; no evidence of failed payments |
| MonthlyCharges | finite, nonnegative numeric | Current listed monthly charge; source currency not independently verified; dashboard dollar sign is a display assumption |
| TotalCharges | finite, nonnegative numeric or blank | Cumulative charge; 11 blanks at zero tenure; retain missing values for train-fit median imputation |
| Churn | Yes / No | Historical target only; disallowed in scoring inputs |

Source columns are not in a meaningful time order. Cumulative TotalCharges need not equal current MonthlyCharges × tenure. Pricing changes and partial periods are unavailable. Imputation is a model transformation, not a claim that the imputed value was observed.

## Scoring input contract

Required columns, with no extras:

```text
customerID,tenure,MonthlyCharges,TotalCharges,PhoneService,MultipleLines,InternetService,OnlineSecurity,OnlineBackup,DeviceProtection,TechSupport,StreamingTV,StreamingMovies,Contract,PaperlessBilling,PaymentMethod,Active
```

`Active` is a supplied eligibility indicator (Yes/No), never a model input. Production data owners must define it using dated operational records. The demonstration derives it from historical `Churn = No` **after** model selection and evaluation, only among holdout accounts. This prevents training overlap but does not create a new prospective test.

Missing IDs, missing status/target, duplicate IDs, empty files, malformed CSV, extra columns, unknown categories, nonfinite/negative charges, fractional tenure, and conflicting service combinations reject the whole batch. No record is silently dropped. Missing predictors produce counted warnings; the saved pipeline imputes using training statistics. If a missing predictor is a playbook-required signal, the customer is excluded from task creation. Unknown categories are rejected at the contract, even though one-hot encoding tolerates them as a second defensive layer.

Raw file hashes capture exact bytes. The reproducible download refuses to replace the bundled file if its hash differs. All derived CSVs are modified outputs, never replacements for raw data.

## Derived fields and denominators

| Field / metric | Definition |
|---|---|
| churn share | Count of Churn=Yes / all reference customers in the selected segment |
| active reference customers | Count of source Churn=No |
| active monthly charges | Sum of MonthlyCharges over source Churn=No; not MRR |
| risk score | Calibrated historical-label model estimate on a 0–1 scale; not a future-event probability |
| risk band | High ≥0.65; Medium ≥0.35 and <0.65; otherwise Low; YAML-configurable |
| queue monthly charges | Current scored snapshot charges for open task IDs present in that snapshot; historical task IDs missing from current input contribute nothing |
| task priority | 1 for High, 2 for Medium, 3 for Low; then descending score and stable customer-ID tie-break |
| due date | UTC pipeline date + configured calendar days; not business-day logic |
| weekly capacity | Maximum tasks created in a UTC Monday-to-Monday week; closed tasks still consume their creation week's capacity |
| eligibility | Snapshot reason from the most recent successful run; live task status is displayed separately |
| top-k precision | Positive holdout labels among the top k scores / k |
| top-k lift | Top-k precision / overall holdout positive share |
| outcomes | Explicit user-entered simulation observations; no manufactured success rate |

Reference analysis is labeled separately from newly uploaded scoring inputs. Pipeline timestamps show processing freshness, not source observation freshness.
