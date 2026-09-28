"""One locked holdout; selection and explanations use validation only."""
from datetime import datetime, timezone
import hashlib
import json
import platform
import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.calibration import CalibratedClassifierCV, calibration_curve
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (average_precision_score, brier_score_loss, confusion_matrix,
    f1_score, precision_score, recall_score, roc_auc_score, roc_curve, precision_recall_curve)
from sklearn.model_selection import train_test_split, StratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from .data import NUMERIC, CAT_FEATURES, FEATURES, feature_frame, load_csv, analyze, json_write, file_hash
from .paths import ROOT, ensure_dirs

SEED = 42

def preprocessing():
    return ColumnTransformer([
        ("numeric", Pipeline([("impute", SimpleImputer(strategy="median")), ("scale", StandardScaler())]), NUMERIC),
        ("category", Pipeline([("impute", SimpleImputer(strategy="most_frequent")),
            ("encode", OneHotEncoder(handle_unknown="ignore", sparse_output=False))]), CAT_FEATURES)
    ], remainder="drop")

def metrics(y, p, threshold, top_fraction=.1):
    pred = p >= threshold
    k = max(1, int(np.ceil(len(y)*top_fraction)))
    # Stable ranking makes tied-score metrics reproducible (including the dummy).
    top = np.argsort(-p, kind="stable")[:k]
    precision_k = float(np.asarray(y)[top].mean())
    return {"n": len(y), "positives": int(np.sum(y)), "threshold": float(threshold),
        "precision": float(precision_score(y, pred, zero_division=0)),
        "recall": float(recall_score(y, pred, zero_division=0)), "f1": float(f1_score(y, pred, zero_division=0)),
        "roc_auc": float(roc_auc_score(y, p)), "pr_auc": float(average_precision_score(y, p)),
        "brier": float(brier_score_loss(y, p)), "confusion_matrix": confusion_matrix(y, pred, labels=[0,1]).tolist(),
        "top_k": k, "precision_at_k": precision_k, "lift_at_k": precision_k/float(np.mean(y)),
        "selected_count": int(np.sum(pred))}

def train(root=ROOT):
    ensure_dirs(root)
    df, issues = load_csv(root / "data/raw/telco.csv")
    y = df.Churn.eq("Yes").astype(int)
    trainval, holdout = train_test_split(df.index, test_size=.2, random_state=SEED, stratify=y)
    train_ids, val_ids = train_test_split(trainval, test_size=.25, random_state=SEED, stratify=y.loc[trainval])
    assert not (set(train_ids) & set(val_ids) or set(train_ids) & set(holdout) or set(val_ids) & set(holdout))
    X = feature_frame(df)
    cv = StratifiedKFold(n_splits=3, shuffle=True, random_state=SEED)
    models = {
        "Prior baseline": Pipeline([("prepare", preprocessing()), ("classifier", DummyClassifier(strategy="prior"))]),
        "Calibrated logistic regression": CalibratedClassifierCV(Pipeline([("prepare", preprocessing()),
            ("classifier", LogisticRegression(C=1., class_weight="balanced", max_iter=1500, random_state=SEED))]), method="sigmoid", cv=cv),
        "Calibrated random forest": CalibratedClassifierCV(Pipeline([("prepare", preprocessing()),
            ("classifier", RandomForestClassifier(n_estimators=160, max_depth=8, min_samples_leaf=12,
                class_weight="balanced_subsample", n_jobs=2, random_state=SEED))]), method="sigmoid", cv=cv)
    }
    validation = {}
    for name, candidate in models.items():
        print(f"Fitting {name}...", flush=True)
        candidate.fit(X.loc[train_ids], y.loc[train_ids])
        p = candidate.predict_proba(X.loc[val_ids])[:,1]
        validation[name] = metrics(y.loc[val_ids], p, .5)
    best = max(validation, key=lambda name: validation[name]["pr_auc"])
    simple = "Calibrated logistic regression"
    selected = simple if validation[simple]["pr_auc"] >= validation[best]["pr_auc"] - .015 else best
    model = models[selected]
    p_val = model.predict_proba(X.loc[val_ids])[:,1]
    # Fixed planning assumption: 100 of 1,000 weekly accounts. Neither the
    # denominator nor the evaluation threshold uses holdout outcomes.
    import yaml
    config = yaml.safe_load((root / "config/playbook.yaml").read_text())
    fraction = min(1., config["weekly_capacity"] / config["evaluation_pool_size"])
    top_n = max(1, int(np.ceil(len(val_ids)*fraction)))
    threshold = float(np.sort(p_val)[-top_n])
    # Final holdout is touched only after model, calibration method, and threshold are fixed.
    p_test = model.predict_proba(X.loc[holdout])[:,1]
    final = metrics(y.loc[holdout], p_test, threshold, fraction)
    actual, predicted = calibration_curve(y.loc[holdout], p_test, n_bins=8, strategy="quantile")
    importance = permutation_importance(model, X.loc[val_ids], y.loc[val_ids], scoring="average_precision",
        n_repeats=5, random_state=SEED, n_jobs=2)
    fpr, tpr, _ = roc_curve(y.loc[holdout], p_test)
    pp, rr, _ = precision_recall_curve(y.loc[holdout], p_test)
    def downsample(a, b):
        idx = np.unique(np.linspace(0,len(a)-1,min(100,len(a))).astype(int))
        return [[float(a[i]),float(b[i])] for i in idx]
    rng = np.random.default_rng(SEED)
    boot = []
    test_y = y.loc[holdout].to_numpy()
    for _ in range(200):
        idx = rng.integers(0,len(test_y),len(test_y))
        if len(np.unique(test_y[idx])) == 2:
            boot.append([roc_auc_score(test_y[idx],p_test[idx]), average_precision_score(test_y[idx],p_test[idx])])
    version = "model-" + hashlib.sha256((file_hash(root/"data/raw/telco.csv") + selected + sklearn.__version__ + str(fraction) + "recipe-v2").encode()).hexdigest()[:12]
    dest = root/"artifacts"/version
    dest.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, dest/"model.joblib")
    evaluation = {
        "version": version, "selected": selected, "created_at": datetime.now(timezone.utc).isoformat(),
        "seed": SEED, "features": FEATURES, "raw_sha256": file_hash(root/"data/raw/telco.csv"),
        "runtime": {"python": platform.python_version(), "sklearn": sklearn.__version__, "pandas": pd.__version__, "numpy": np.__version__},
        "split": {"train": len(train_ids), "validation": len(val_ids), "holdout": len(holdout)},
        "validation": validation, "selection_rule": "Highest validation average precision; prefer calibrated logistic regression within 0.015 of best.",
        "holdout": final, "capacity_fraction": fraction, "weekly_capacity_at_training": config["weekly_capacity"], "evaluation_pool_size": config["evaluation_pool_size"],
        "calibration": [{"mean_score": float(p), "observed_fraction": float(a)} for p,a in zip(predicted,actual)],
        "roc_curve": downsample(fpr,tpr), "pr_curve": downsample(rr,pp),
        "bootstrap_95": {"roc_auc": np.quantile(np.array(boot)[:,0],[.025,.975]).tolist(), "pr_auc": np.quantile(np.array(boot)[:,1],[.025,.975]).tolist()},
        "importance": sorted([{"feature": f, "ap_drop": float(m), "std": float(s)} for f,m,s in zip(FEATURES, importance.importances_mean, importance.importances_std)], key=lambda r:-r["ap_drop"]),
        "limitations": ["Fictional, undated snapshot: no validated future prediction horizon.",
            "Random stratified split does not measure temporal generalization.", "Scores are calibrated historical-label estimates; use as ranking signals for this demo.",
            "Feature availability before churn cannot be established from this snapshot.",
            "No evidence of causal retention impact; service subscriptions are not usage or support incidents."]
    }
    json_write(dest/"evaluation.json",evaluation)
    for name, ids in [("train", train_ids),("validation", val_ids),("holdout",holdout)]:
        df.loc[ids].to_csv(root/f"data/training/{name}.csv", index=False)
    json_write(root/"data/training/split_manifest.json", {name: df.loc[ids,"customerID"].tolist() for name,ids in [("train",train_ids),("validation",val_ids),("holdout",holdout)]})
    active_demo = df.loc[holdout].query("Churn == 'No'")
    scoring = active_demo[["customerID",*FEATURES]].copy()
    scoring["Active"] = "Yes"
    scoring.to_csv(root/"data/scoring/active_customers.csv",index=False)
    df.to_csv(root/"data/processed/reference.csv",index=False)
    summary = analyze(df)
    json_write(root/"reports/analysis.json",summary)
    json_write(root/"reports/validation.json",issues)
    json_write(root/"artifacts/current.json", {"version":version})
    return evaluation

def load_model(root=ROOT):
    version = json.loads((root/"artifacts/current.json").read_text())["version"]
    # Artifacts must be locally generated/trusted: joblib can execute code while loading.
    path = root/"artifacts"/version
    meta = json.loads((path/"evaluation.json").read_text())
    return joblib.load(path/"model.joblib"), meta
