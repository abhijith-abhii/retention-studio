"""SQLite is authoritative; all workflow mutations are audited and transactional."""
import csv
from datetime import datetime, timezone
import io
import json
import sqlite3
import time
from .playbook import STATUSES, TRANSITIONS

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
 id TEXT PRIMARY KEY, started_at TEXT NOT NULL, finished_at TEXT, status TEXT NOT NULL,
 input_name TEXT NOT NULL, input_hash TEXT, model_version TEXT, playbook_version TEXT,
 rows_count INTEGER DEFAULT 0, created_count INTEGER DEFAULT 0, details TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS batches (fingerprint TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES runs(id));
CREATE TABLE IF NOT EXISTS customers (customer_id TEXT PRIMARY KEY, score REAL NOT NULL, risk_band TEXT NOT NULL,
 payload TEXT NOT NULL, run_id TEXT NOT NULL REFERENCES runs(id));
CREATE TABLE IF NOT EXISTS tasks (
 id INTEGER PRIMARY KEY, customer_id TEXT NOT NULL, score REAL NOT NULL, risk_band TEXT NOT NULL,
 action TEXT NOT NULL, rule_id TEXT NOT NULL, rationale TEXT NOT NULL, signals TEXT NOT NULL, draft TEXT NOT NULL,
 priority INTEGER NOT NULL, owner TEXT NOT NULL, due_date TEXT NOT NULL, status TEXT NOT NULL
 CHECK(status IN ('New','Assigned','In Progress','Completed','Dismissed')),
 model_version TEXT NOT NULL, playbook_version TEXT NOT NULL, config_hash TEXT NOT NULL,
 run_id TEXT NOT NULL REFERENCES runs(id), created_at TEXT NOT NULL, updated_at TEXT NOT NULL, contacted_at TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_tasks_open_customer ON tasks(customer_id)
 WHERE status NOT IN ('Completed','Dismissed');
CREATE INDEX IF NOT EXISTS idx_tasks_customer ON tasks(customer_id);
CREATE INDEX IF NOT EXISTS idx_tasks_created ON tasks(created_at);
CREATE TABLE IF NOT EXISTS audit (
 id INTEGER PRIMARY KEY, task_id INTEGER NOT NULL REFERENCES tasks(id), at TEXT NOT NULL,
 event TEXT NOT NULL, before_value TEXT, after_value TEXT NOT NULL, actor TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS outcomes (
 task_id INTEGER PRIMARY KEY REFERENCES tasks(id), result TEXT NOT NULL,
 notes TEXT NOT NULL, observed_at TEXT NOT NULL, followup_date TEXT, simulation INTEGER NOT NULL DEFAULT 1
);
"""

def connect(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=30)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    # First-open journal-mode changes can raise SQLITE_BUSY before SQLite's
    # normal busy handler takes effect. Retry only initialization lock errors.
    for attempt in range(7):
        try:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript(SCHEMA)
            break
        except sqlite3.OperationalError as exc:
            if "locked" not in str(exc).lower() or attempt == 6:
                db.close()
                raise
            time.sleep(min(.05 * 2**attempt, 1.))
    return db

def rows(db, query, params=()):
    return [dict(r) for r in db.execute(query,params).fetchall()]

def queue(db):
    tasks = rows(db,"SELECT * FROM tasks ORDER BY CASE WHEN status IN ('Completed','Dismissed') THEN 1 ELSE 0 END, priority, score DESC, customer_id")
    for t in tasks: t["signals"] = json.loads(t["signals"])
    return tasks

def queue_csv(tasks):
    buf = io.StringIO()
    fields = ["id","customer_id","score","risk_band","action","rationale","priority","owner","due_date","status","model_version","playbook_version","created_at","contacted_at"]
    writer = csv.DictWriter(buf,fieldnames=fields,extrasaction="ignore")
    writer.writeheader()
    for t in tasks:
        # Spreadsheet formula injection defense for user-editable text fields.
        writer.writerow({k: ("'"+v if isinstance(v,str) and v.startswith(("=","+","-","@")) else v) for k,v in t.items()})
    return buf.getvalue()

def update_task(db, task_id, status, owner, expected_updated_at=None, now=None):
    now = now or datetime.now(timezone.utc)
    if status not in STATUSES: raise ValueError("Unknown workflow status.")
    if not isinstance(owner,str) or not owner.strip() or len(owner)>80: raise ValueError("Owner must contain 1–80 characters.")
    with db:
        db.execute("BEGIN IMMEDIATE")
        old = db.execute("SELECT * FROM tasks WHERE id=?",(task_id,)).fetchone()
        if old is None: raise LookupError("Task not found.")
        if expected_updated_at and old["updated_at"] != expected_updated_at: raise ValueError("Task changed in another session. Refresh before saving.")
        if status != old["status"] and status not in TRANSITIONS[old["status"]]: raise ValueError("This status transition is not allowed; closed tasks remain closed.")
        db.execute("UPDATE tasks SET status=?,owner=?,updated_at=? WHERE id=?", (status,owner.strip(),now.isoformat(),task_id))
        before = json.dumps({"status":old["status"],"owner":old["owner"]})
        after = json.dumps({"status":status,"owner":owner.strip()})
        db.execute("INSERT INTO audit(task_id,at,event,before_value,after_value,actor) VALUES(?,?,?,?,?,?)",(task_id,now.isoformat(),"workflow_updated",before,after,"local user (simulation)"))

OUTCOMES = ["Contacted — awaiting response", "No response", "Retained at follow-up", "Churned at follow-up", "Not contacted"]

def record_outcome(db, task_id, result, notes, observed_at, followup_date, now=None):
    now = now or datetime.now(timezone.utc)
    if result not in OUTCOMES: raise ValueError("Unknown outcome.")
    if not isinstance(notes,str) or len(notes)>2000: raise ValueError("Notes must be at most 2,000 characters.")
    try:
        observed = datetime.fromisoformat(observed_at).date()
        followup = datetime.fromisoformat(followup_date).date() if followup_date else None
    except (ValueError,TypeError) as exc: raise ValueError("Use valid ISO dates.") from exc
    if observed > now.date(): raise ValueError("An observed outcome cannot be dated in the future.")
    if followup and followup < observed: raise ValueError("Follow-up cannot precede the observation.")
    with db:
        db.execute("BEGIN IMMEDIATE")
        task = db.execute("SELECT * FROM tasks WHERE id=?",(task_id,)).fetchone()
        if task is None: raise LookupError("Task not found.")
        old = db.execute("SELECT * FROM outcomes WHERE task_id=?",(task_id,)).fetchone()
        db.execute("INSERT INTO outcomes(task_id,result,notes,observed_at,followup_date,simulation) VALUES(?,?,?,?,?,1) ON CONFLICT(task_id) DO UPDATE SET result=excluded.result,notes=excluded.notes,observed_at=excluded.observed_at,followup_date=excluded.followup_date",(task_id,result,notes,observed.isoformat(),followup.isoformat() if followup else None))
        if result != "Not contacted":
            # Actual contact time is not supplied by the sample; recording time starts a conservative cooldown.
            db.execute("UPDATE tasks SET contacted_at=?,updated_at=? WHERE id=?",(now.isoformat(),now.isoformat(),task_id))
        db.execute("INSERT INTO audit(task_id,at,event,before_value,after_value,actor) VALUES(?,?,?,?,?,?)",(task_id,now.isoformat(),"simulated_outcome_recorded",json.dumps(dict(old)) if old else None,json.dumps({"result":result,"notes":notes,"observed_at":observed.isoformat(),"followup_date":followup_date}),"local user (simulation)"))
