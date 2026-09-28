from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
import hashlib
import json
import uuid
from .data import load_csv, feature_frame, file_hash, json_write, ValidationError
from .model import load_model
from .paths import ROOT, ensure_dirs
from .playbook import load_config, exclusion, recommendation, band
from .store import connect, rows, queue, queue_csv

def run_pipeline(input_path=None, root=ROOT, now=None):
    ensure_dirs(root)
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None: raise ValueError("Pipeline time must be timezone-aware.")
    now = now.astimezone(timezone.utc)
    input_path = input_path or root/"data/scoring/active_customers.csv"
    run_id = "run-" + uuid.uuid4().hex[:12]
    db = connect(root/"var/retention.sqlite")
    db.execute("INSERT INTO runs(id,started_at,status,input_name) VALUES(?,?,?,?)",(run_id,now.isoformat(),"Running",input_path.name))
    db.commit()
    try:
        config = load_config(root/"config/playbook.yaml")
        df, issues = load_csv(input_path,scoring=True)
        model, meta = load_model(root)
        input_hash = file_hash(input_path)
        fingerprint = hashlib.sha256((input_hash+meta["version"]+config["fingerprint"]).encode()).hexdigest()
        df["score"] = model.predict_proba(feature_frame(df))[:,1]
        df = df.sort_values(["score","customerID"], ascending=[False,True], kind="stable")
        with db:
            db.execute("BEGIN IMMEDIATE")
            previous = db.execute("SELECT run_id FROM batches WHERE fingerprint=?",(fingerprint,)).fetchone()
            if previous:
                result = {"run_id":run_id,"status":"Skipped","created":0,"reason":"Identical successful input, model, and playbook already processed.","original_run":previous[0]}
                db.execute("UPDATE runs SET status='Skipped',finished_at=?,input_hash=?,model_version=?,playbook_version=?,rows_count=?,details=? WHERE id=?",(datetime.now(timezone.utc).isoformat(),input_hash,meta["version"],config["version"],len(df),json.dumps(result),run_id))
                return result
            history = defaultdict(list)
            for t in rows(db,"SELECT * FROM tasks"): history[t["customer_id"]].append(t)
            week_start = (now-timedelta(days=now.weekday())).replace(hour=0,minute=0,second=0,microsecond=0)
            week_end = week_start+timedelta(days=7)
            used = db.execute("SELECT COUNT(*) FROM tasks WHERE created_at>=? AND created_at<?",(week_start.isoformat(),week_end.isoformat())).fetchone()[0]
            remaining = max(0,config["weekly_capacity"]-used)
            exclusions = Counter()
            created, candidate_count, cutoff = 0,0,None
            db.execute("DELETE FROM customers")
            for _, row in df.iterrows():
                reason = exclusion(row,config,history[row.customerID],now)
                rec = recommendation(row,config) if reason is None else None
                if reason is None and rec is None: reason = "No matching rule"
                if reason is None:
                    candidate_count += 1
                    if created >= remaining: reason = "Weekly capacity reached"
                risk = band(row.score,config)
                payload = json.loads(row.to_json())
                payload.update({"eligibility":reason or "Selected for outreach", "recommendation":rec})
                db.execute("INSERT INTO customers VALUES(?,?,?,?,?)",(row.customerID,float(row.score),risk,json.dumps(payload),run_id))
                if reason:
                    exclusions[reason] += 1
                    continue
                priority = 1 if risk == "High" else 2 if risk == "Medium" else 3
                values = {"customer_id":row.customerID,"score":float(row.score),"risk_band":risk,
                    **{k:rec[k] for k in ["action","rule_id","rationale","draft","owner"]},"signals":json.dumps(rec["signals"]),
                    "priority":priority,"due_date":(now+timedelta(days=config["due_in_days"])).date().isoformat(),"status":"New",
                    "model_version":meta["version"],"playbook_version":config["version"],"config_hash":config["fingerprint"],
                    "run_id":run_id,"created_at":now.isoformat(),"updated_at":now.isoformat()}
                fields = ",".join(values)
                cursor = db.execute(f"INSERT INTO tasks({fields}) VALUES({','.join('?' for _ in values)})",tuple(values.values()))
                db.execute("INSERT INTO audit(task_id,at,event,after_value,actor) VALUES(?,?,?,?,?)",(cursor.lastrowid,now.isoformat(),"recommendation_created",json.dumps(values),"pipeline (simulation)"))
                created += 1
                cutoff = float(row.score)
            result = {"run_id":run_id,"status":"Success","created":created,"rows":len(df),"issues":issues,
                "exclusions":dict(exclusions),"eligible_before_capacity":candidate_count,"weekly_capacity":config["weekly_capacity"],
                "capacity_used_before_run":used,"operational_cutoff":cutoff,
                "week_start_utc":week_start.isoformat(),"model_version":meta["version"],"playbook_version":config["version"],
                "simulation":True,"source_sha256":input_hash}
            out = root/"var/runs"/run_id
            out.mkdir(parents=True,exist_ok=True)
            df.to_csv(out/"processed_scores.csv",index=False)
            (out/"action_queue.csv").write_text(queue_csv(queue(db)))
            json_write(out/"execution.json",result)
            json_write(out/"playbook.json",config)
            (out/"notification-summary.txt").write_text(f"SIMULATION — NOT SENT\n{created} new review tasks from {len(df)} customer records.\nModel: {meta['version']}\nPlaybook: {config['version']}\nReview the local dashboard. No external messages, discounts, or account changes occurred.\n")
            db.execute("INSERT INTO batches VALUES(?,?)",(fingerprint,run_id))
            db.execute("UPDATE runs SET status='Success',finished_at=?,input_hash=?,model_version=?,playbook_version=?,rows_count=?,created_count=?,details=? WHERE id=?",(datetime.now(timezone.utc).isoformat(),input_hash,meta["version"],config["version"],len(df),created,json.dumps(result),run_id))
        return result
    except Exception as exc:
        db.rollback()
        details = {"error":str(exc),"issues":getattr(exc,"issues",[]),"last_success_preserved":True}
        with db:
            db.execute("UPDATE runs SET status='Failed',finished_at=?,details=? WHERE id=?",(datetime.now(timezone.utc).isoformat(),json.dumps(details),run_id))
        json_write(root/"var/runs"/run_id/"execution.json",details)
        raise
    finally:
        db.close()
