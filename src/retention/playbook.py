from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
import pandas as pd
import yaml
from .data import FEATURES

STATUSES = ["New", "Assigned", "In Progress", "Completed", "Dismissed"]
TERMINAL = ["Completed", "Dismissed"]
TRANSITIONS = {"New": ["Assigned", "In Progress", "Completed", "Dismissed"],
    "Assigned": ["In Progress", "Completed", "Dismissed"], "In Progress": ["Completed", "Dismissed"],
    "Completed": [], "Dismissed": []}

def load_config(path):
    c = yaml.safe_load(path.read_text())
    if not isinstance(c, dict): raise ValueError("Playbook must be a YAML mapping.")
    if c.get("simulation_only") is not True: raise ValueError("Only simulation mode is implemented. No external sending integration exists.")
    for key in ["weekly_capacity", "cooldown_days", "due_in_days"]:
        if type(c.get(key)) is not int or c[key] < 0: raise ValueError(f"{key} must be a non-negative integer.")
    if type(c.get("evaluation_pool_size")) is not int or c["evaluation_pool_size"] <= 0:
        raise ValueError("evaluation_pool_size must be a positive planning denominator.")
    for key in ["minimum_score", "medium_risk_score", "high_risk_score"]:
        if not isinstance(c.get(key), (int,float)) or not 0 <= c[key] <= 1: raise ValueError(f"{key} must be between 0 and 1.")
    if c["medium_risk_score"] >= c["high_risk_score"]: raise ValueError("Risk band boundaries must increase.")
    if not set(c.get("required_signals",[])) <= set(FEATURES): raise ValueError("Required signals must be verified feature fields.")
    if not isinstance(c.get("excluded_customers"), list): raise ValueError("excluded_customers must be a list.")
    if not c.get("version") or not c.get("rules"): raise ValueError("Playbook needs a version and rules.")
    ids = []
    for r in c["rules"]:
        ids.append(r["id"])
        for key in ["action", "owner", "rationale", "conditions"]:
            if key not in r: raise ValueError(f"Missing rule field {key}.")
        for field, conditions in r["conditions"].items():
            if field not in FEATURES or not set(conditions) <= {"eq", "in", "gte", "lte"}: raise ValueError("Invalid rule condition.")
    if len(ids) != len(set(ids)): raise ValueError("Duplicate rule IDs.")
    c["fingerprint"] = hashlib.sha256(json.dumps(c,sort_keys=True).encode()).hexdigest()[:12]
    return c

def band(score, config):
    return "High" if score >= config["high_risk_score"] else "Medium" if score >= config["medium_risk_score"] else "Low"

def matches(row, conditions):
    for field, checks in conditions.items():
        value = row[field]
        if pd.isna(value): return False
        for op, target in checks.items():
            if op == "eq" and value != target: return False
            if op == "in" and value not in target: return False
            if op == "gte" and value < target: return False
            if op == "lte" and value > target: return False
    return True

def exclusion(row, config, history, now):
    if row.Active != "Yes": return "Inactive customer"
    if row.customerID in config["excluded_customers"]: return "Excluded by playbook"
    if any(pd.isna(row[c]) for c in config["required_signals"]): return "Missing required playbook signal"
    if not math.isfinite(row.score) or row.score < config["minimum_score"]: return "Below minimum score"
    for task in history:
        if task["status"] not in TERMINAL: return "Open task already exists"
        last = datetime.fromisoformat(task.get("contacted_at") or task["updated_at"])
        if now - last < timedelta(days=config["cooldown_days"]): return "Contact cooldown"
    return None

def recommendation(row, config):
    for rule in config["rules"]:
        if rule.get("enabled",True) and matches(row,rule["conditions"]):
            signals = [f"Tenure: {row.tenure:g} months", f"Contract: {row.Contract}",
                       f"Monthly charge: {row.MonthlyCharges:.2f}", f"Payment: {row.PaymentMethod}",
                       f"Internet: {row.InternetService}", f"Technical-support add-on: {row.TechSupport}"]
            draft = (f"Hello,\n\nI’m reaching out about account {row.customerID}. Our records show a {row.Contract.lower()} "
                f"subscription with monthly charges of {row.MonthlyCharges:.2f}. "
                + {"onboarding": "Would you like help getting set up or using your services?",
                   "billing": "Would a walkthrough of your current bill and available payment options be helpful?",
                   "education": "Would you like information about the help resources available for your internet service?",
                   "offer": "Would you be interested in a review of any options you may qualify for?"}.get(rule["id"], "Would you like to review whether your current plan fits your needs?")
                + "\n\nThank you,\nCustomer care\n\n[SIMULATION DRAFT — verify current details and contact permission before use.]")
            return {"rule_id": rule["id"], "action": rule["action"], "owner": rule["owner"],
                "rationale": rule["rationale"], "signals": signals, "draft": draft}
    return None
