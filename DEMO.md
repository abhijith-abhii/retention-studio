# Five-minute demonstration

1. **Open the overview (40 seconds).** Explain the 7,043 fictional reference customers, historical churn share, and separate 1,035-account active scoring pool. Charges provide account context; they are not saved revenue.
2. **Explain a segment (40 seconds).** In Churn analysis, switch from Contract to Tenure band. Read the numerator and denominator. Explain that short tenure is associated with churn; the app cannot show that onboarding will prevent churn.
3. **Defend the model (60 seconds).** In Model performance, show three candidates, the disjoint split sizes, final holdout average precision, calibration curve, and recall at the fixed capacity-derived threshold. Contrast fixed evaluation cutoff with the operational queue cutoff.
4. **Review a customer (60 seconds).** Search for `8161-QYMTT` in Customer explorer. Inspect the billing-support rule, recorded monthly charge/payment method, and simulation draft. Set the task to Assigned or In Progress and save. Close, reload, and reopen to show persistence and the audit trail. Do not claim a bill was overdue or a message was sent.
5. **Show repeatability (40 seconds).** Click Run pipeline twice. Once this input/model/config is successful, subsequent runs show Skipped with zero new tasks. Open Pipeline history, inspect the run, and download the queue CSV.
6. **Close with measurement (40 seconds).** Outcomes starts empty. Describe random assignment to outreach/control and a predeclared observation window using future dated production data. The optional calculator displays hypothetical net value, not achieved ROI.

Optional: record a deliberate simulation observation using a task's outcome form. It persists and appears in Outcomes with a Simulation label. This modifies your local demonstration state; no observation is prefilled as a success, and no external message is sent.

For an invalid-input demo, copy the downloaded scoring CSV, change a Contract value to `Unknown`, and upload it in Pipeline history. The run fails visibly; the last good customer snapshot and task queue remain. Do this only with a disposable sample file, never credentials or private customer data.

The startup command is `./start.sh`; leave its terminal running. Local scheduling is not enabled. Integration, consent, production dates, and causal retention measurement are future work.
