# Customer churn analysis

## Business question and scope

A fictional subscription telecom team needs to understand which accounts resemble historical churners, decide which active accounts to review, and track its work. This project supports prioritization and operational learning; it does not demonstrate that outreach prevents churn.

## Observed facts in the sample

- 7,043 unique customer records; 1,869 labeled Churn = Yes (26.54%); 5,174 labeled No.
- Active reference accounts have 316,985.75 in listed monthly charges. This sum is not realized revenue, MRR, expected loss, or recoverable value.
- 11 total-charge values are blank and occur at zero tenure. They remain missing in cleaned data; model preprocessing imputes using training-fold medians.

Churn is defined as the supplied binary Yes label. No is treated as active for the simulation. The CSV has no observation dates or dated churn events, so the report calls this an observed snapshot share, not a measured monthly churn rate. The data describes a fictional company. All numbers are properties of the sample, not a real business.

## Segment evidence

| Dimension | Segment | Churn / customers | Share | 95% Wilson interval |
|---|---|---:|---:|---:|
| Contract | Month-to-month | 1,655 / 3,875 | 42.7% | 41.2%–44.3% |
| Contract | One year | 166 / 1,473 | 11.3% | 9.8%–13.0% |
| Contract | Two year | 48 / 1,695 | 2.8% | 2.1%–3.7% |
| Tenure band | 0–6 months | 784 / 1,481 | 52.9% | 50.4%–55.5% |
| Tenure band | 7–12 months | 253 / 705 | 35.9% | 32.4%–39.5% |
| Tenure band | 13–24 months | 294 / 1,024 | 28.7% | 26.0%–31.6% |
| Tenure band | 25–48 months | 325 / 1,594 | 20.4% | 18.5%–22.4% |
| Tenure band | 49+ months | 213 / 2,239 | 9.5% | 8.4%–10.8% |
| InternetService | DSL | 459 / 2,421 | 19.0% | 17.4%–20.6% |
| InternetService | Fiber optic | 1,297 / 3,096 | 41.9% | 40.2%–43.6% |
| InternetService | No | 113 / 1,526 | 7.4% | 6.2%–8.8% |
| PaymentMethod | Bank transfer (automatic) | 258 / 1,544 | 16.7% | 14.9%–18.7% |
| PaymentMethod | Credit card (automatic) | 232 / 1,522 | 15.2% | 13.5%–17.1% |
| PaymentMethod | Electronic check | 1,071 / 2,365 | 45.3% | 43.3%–47.3% |
| PaymentMethod | Mailed check | 308 / 1,612 | 19.1% | 17.3%–21.1% |
| TechSupport | No | 1,446 / 3,473 | 41.6% | 40.0%–43.3% |
| TechSupport | No internet service | 113 / 1,526 | 7.4% | 6.2%–8.8% |
| TechSupport | Yes | 310 / 2,044 | 15.2% | 13.7%–16.8% |
| Charge band | 0–40 inclusive | 214 / 1,838 | 11.6% | 10.3%–13.2% |
| Charge band | Over 40–70 | 388 / 1,622 | 23.9% | 21.9%–26.1% |
| Charge band | Over 70–100 | 1,014 / 2,681 | 37.8% | 36.0%–39.7% |
| Charge band | Over 100 | 253 / 902 | 28.0% | 25.2%–31.1% |

## Actions worth testing

1. **Early-tenure onboarding:** the shortest-tenure segment has the highest observed churn share. Offer setup assistance to eligible early-tenure accounts, then measure results with a control group.
2. **Plan-fit conversations:** month-to-month customers have a much higher churn share than annual-contract customers. Customer selection, tenure, pricing, and contract terms may confound this comparison; moving customers to longer contracts is not proven to prevent churn.
3. **Billing clarity:** electronic-check payment is associated with churn. For eligible higher-charge accounts, offer a bill walkthrough. Do not infer failed payments, financial distress, or dissatisfaction.
4. **Product education:** the technical-support field is a subscribed add-on, not evidence of support tickets. Explain available help without inventing incidents or service failures.

## Data and interpretation limits

- No behavioral usage, support incidents, contact permission, channel details, margin, discounts, or dated outcomes are provided.
- Segment shares use all observed customers in that segment as the denominator. Wilson intervals do not account for selection bias, confounding, multiple comparisons, or fictional data generation.
- Segments under 50 customers are flagged by the application. The displayed reference segments exceed this minimum, but that does not establish external validity.
- Demographics are excluded from scoring and recommendations. Proxy bias is still possible; no claim of fairness is made.
- Monetary values retain source numeric units. The dashboard uses a dollar sign as a presentation assumption; currency is not independently verified in the CSV.
- TotalCharges is a cumulative field. It is not expected to equal current MonthlyCharges × tenure because historical prices and partial periods are unavailable. The validator rejects negative/nonfinite values, fractional tenure, positive totals at zero tenure, and inconsistent service categories; it does not impose that unsupported equality.

## Source

[IBM source repository](https://github.com/IBM/telco-customer-churn-on-icp4d), pinned in `data/raw/source.json`. The original CSV is redistributed unchanged with the repository’s Apache-2.0 license and attribution. See DATA.md for provenance and permissions.
