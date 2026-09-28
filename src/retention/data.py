"""Strict snapshot contracts. Target and identity are never model features."""
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd

NUMERIC = ["tenure", "MonthlyCharges", "TotalCharges"]
BINARY = ["Partner", "Dependents", "PhoneService", "PaperlessBilling"]
SERVICES = ["OnlineSecurity", "OnlineBackup", "DeviceProtection", "TechSupport", "StreamingTV", "StreamingMovies"]
CATEGORIES = {
    "gender": ["Female", "Male"], "SeniorCitizen": ["0", "1"],
    **{c: ["Yes", "No"] for c in BINARY},
    "MultipleLines": ["Yes", "No", "No phone service"],
    "InternetService": ["DSL", "Fiber optic", "No"],
    **{c: ["Yes", "No", "No internet service"] for c in SERVICES},
    "Contract": ["Month-to-month", "One year", "Two year"],
    "PaymentMethod": ["Electronic check", "Mailed check", "Bank transfer (automatic)", "Credit card (automatic)"],
}
CAT_FEATURES = ["PhoneService", "MultipleLines", "InternetService", *SERVICES, "Contract", "PaperlessBilling", "PaymentMethod"]
FEATURES = NUMERIC + CAT_FEATURES
RAW_COLUMNS = ["customerID", *CATEGORIES, *NUMERIC, "Churn"]
SCORING_COLUMNS = ["customerID", *FEATURES, "Active"]
FORBIDDEN = {"Churn", "Churn Reason", "Churn Score", "Churn Value", "Customer Status", "CLTV", "customerID", "Active"}

class ValidationError(ValueError):
    def __init__(self, issues):
        self.issues = issues
        super().__init__("; ".join(i["message"] for i in issues if i["severity"] == "error"))

def validate(df, scoring=False):
    """Reject ambiguous records; leave allowed missing predictors for train-fit imputation."""
    df = df.copy()
    issues = []
    def add(severity, message, count=1):
        issues.append({"severity": severity, "message": message, "count": int(count)})
    if df.empty:
        add("error", "Input has no customer rows.")
    required = SCORING_COLUMNS if scoring else RAW_COLUMNS
    missing = sorted(set(required) - set(df.columns))
    if missing:
        add("error", "Missing columns: " + ", ".join(missing))
    extra = sorted(set(df.columns) - set(required))
    if extra:
        add("error", "Unexpected columns (possible leakage): " + ", ".join(extra))
    if any(i["severity"] == "error" for i in issues):
        raise ValidationError(issues)
    for col in df:
        df[col] = df[col].map(lambda v: v.strip() if isinstance(v, str) else v)
        df[col] = df[col].replace("", np.nan)
    ids = df.customerID
    if ids.isna().any(): add("error", "Missing customer identifiers.", ids.isna().sum())
    if ids.duplicated().any(): add("error", "Duplicate customer identifiers.", ids.duplicated().sum())
    if (~ids.fillna("").astype(str).str.fullmatch(r"[A-Za-z0-9_-]{1,64}")).any():
        add("error", "Customer identifiers must be 1–64 letters, numbers, underscores, or hyphens.")
    for col in NUMERIC:
        raw = df[col]
        parsed = pd.to_numeric(raw, errors="coerce")
        invalid = raw.notna() & (parsed.isna() | ~np.isfinite(parsed))
        if invalid.any(): add("error", f"Invalid numeric values in {col}.", invalid.sum())
        if (parsed < 0).any(): add("error", f"Negative values in {col}.", (parsed < 0).sum())
        df[col] = parsed.astype(float)
    if ((df.tenure.dropna() % 1) != 0).any(): add("error", "Tenure must be a whole number of months.")
    if (df.tenure > 1200).any(): add("error", "Tenure exceeds the 100-year validation boundary.")
    for col, allowed in CATEGORIES.items():
        if col not in df: continue
        if col == "SeniorCitizen": df[col] = df[col].map(lambda x: str(int(float(x))) if str(x) in ["0", "1", "0.0", "1.0"] else x)
        bad = df[col].notna() & ~df[col].isin(allowed)
        if bad.any(): add("error", f"Invalid category in {col}.", bad.sum())
    target = "Active" if scoring else "Churn"
    if (~df[target].isin(["Yes", "No"])).any(): add("error", f"{target} must be Yes or No with no missing values.")
    for col in SERVICES:
        known = df.InternetService.notna() & df[col].notna()
        inconsistent = known & ((df.InternetService == "No") != (df[col] == "No internet service"))
        if inconsistent.any(): add("error", f"{col} conflicts with InternetService.", inconsistent.sum())
    known = df.PhoneService.notna() & df.MultipleLines.notna()
    inconsistent = known & ((df.PhoneService == "No") != (df.MultipleLines == "No phone service"))
    if inconsistent.any(): add("error", "MultipleLines conflicts with PhoneService.", inconsistent.sum())
    # Zero tenure means no billed history in this dataset. Do not fabricate observed charges.
    inconsistent = (df.tenure == 0) & (df.TotalCharges.fillna(0) > 0)
    if inconsistent.any(): add("error", "Positive total charges at zero tenure.", inconsistent.sum())
    for col in FEATURES:
        count = df[col].isna().sum()
        if count: add("warning", f"{col}: missing values retained for training-fit imputation; required playbook signals gate outreach.", count)
    if any(i["severity"] == "error" for i in issues): raise ValidationError(issues)
    # sklearn expects np.nan, not pandas nullable scalar objects.
    for col in CAT_FEATURES: df[col] = df[col].astype(object).where(df[col].notna(), np.nan)
    return df, issues

def load_csv(path, scoring=False):
    try:
        frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    except (pd.errors.EmptyDataError, pd.errors.ParserError, UnicodeDecodeError) as exc:
        raise ValidationError([{"severity": "error", "message": f"Unreadable CSV: {exc}", "count": 1}]) from exc
    return validate(frame, scoring=scoring)

def feature_frame(df):
    assert not (set(FEATURES) & FORBIDDEN), "Leaking feature contract"
    return df.loc[:, FEATURES]

def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def json_write(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False, default=str) + "\n")

def analyze(df):
    d = df.copy()
    d["churned"] = d.Churn.eq("Yes").astype(int)
    d["Tenure band"] = pd.cut(d.tenure, [-1, 6, 12, 24, 48, np.inf], labels=["0–6 months", "7–12 months", "13–24 months", "25–48 months", "49+ months"])
    d["Charge band"] = pd.cut(d.MonthlyCharges, [-1, 40, 70, 100, np.inf], labels=["0–40 inclusive", "Over 40–70", "Over 70–100", "Over 100"])
    dimensions = ["Contract", "Tenure band", "InternetService", "PaymentMethod", "TechSupport", "Charge band"]
    segments = {}
    for dim in dimensions:
        rows = []
        for name, group in d.groupby(dim, observed=True, sort=True, dropna=False):
            n, k = len(group), int(group.churned.sum())
            p, z = k / n, 1.96
            den = 1 + z*z/n
            center = (p+z*z/(2*n))/den
            half = z*np.sqrt(p*(1-p)/n + z*z/(4*n*n))/den
            rows.append({"segment": str(name), "customers": n, "churned": k, "rate": p,
                         "ci_low": max(0, center-half), "ci_high": min(1, center+half), "small": n < 50})
        segments[dim] = rows
    active = d[d.Churn == "No"]
    return {"customers": len(d), "churned": int(d.churned.sum()), "active": len(active),
            "churn_rate": float(d.churned.mean()), "active_monthly_charges": round(float(active.MonthlyCharges.sum()), 2),
            "average_monthly_charge": float(d.MonthlyCharges.mean()), "segments": segments,
            "missing_total_charges": int(d.TotalCharges.isna().sum()),
            "data_label": "IBM fictional telecom sample · undated snapshot", "time_series_available": False}
