from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
import secrets
import sqlite3
import uuid
from flask import Flask, jsonify, render_template, request, session, Response
from werkzeug.exceptions import HTTPException
from .paths import ROOT, ensure_dirs
from .store import connect, rows, queue, queue_csv, update_task, record_outcome, OUTCOMES
from .playbook import load_config, STATUSES
from .pipeline import run_pipeline
from .data import file_hash

def create_app(root=ROOT):
    app = Flask(__name__,static_folder=str(ROOT/"static"),template_folder=str(ROOT/"templates"))
    app.config.update(SECRET_KEY=secrets.token_hex(32), MAX_CONTENT_LENGTH=5*1024*1024,
        SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Strict", TRUSTED_HOSTS=["127.0.0.1","localhost"])
    ensure_dirs(root)

    @app.before_request
    def protect_mutations():
        if request.method in ["POST","PATCH","DELETE"]:
            if not session.get("csrf") or not secrets.compare_digest(request.headers.get("X-CSRF-Token",""),session["csrf"]):
                return jsonify(error="Refresh the dashboard before saving."),403

    @app.after_request
    def headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'"
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/")
    def index():
        session.setdefault("csrf",secrets.token_hex(32))
        return render_template("index.html",csrf=session["csrf"])

    @app.get("/api/health")
    def health(): return jsonify(status="ok",simulation=True)

    @app.get("/api/dashboard")
    def dashboard():
        if not (root/"artifacts/current.json").exists():
            return jsonify(error="No trained model yet. Run the bootstrap command in the README."),503
        version = json.loads((root/"artifacts/current.json").read_text())["version"]
        evaluation = json.loads((root/"artifacts"/version/"evaluation.json").read_text())
        analysis = json.loads((root/"reports/analysis.json").read_text())
        config = load_config(root/"config/playbook.yaml")
        db = connect(root/"var/retention.sqlite")
        try:
            customers = rows(db,"SELECT * FROM customers ORDER BY score DESC,customer_id")
            for c in customers: c["payload"] = json.loads(c["payload"])
            runs = rows(db,"SELECT * FROM runs ORDER BY started_at DESC, rowid DESC LIMIT 100")
            for r in runs: r["details"] = json.loads(r["details"])
            outcomes = rows(db,"SELECT o.*,t.customer_id,t.action,t.status FROM outcomes o JOIN tasks t ON o.task_id=t.id ORDER BY o.observed_at DESC")
            now = datetime.now(timezone.utc)
            week_start = (now-timedelta(days=now.weekday())).replace(hour=0,minute=0,second=0,microsecond=0)
            week_end = week_start+timedelta(days=7)
            weekly_created = db.execute("SELECT COUNT(*) FROM tasks WHERE created_at>=? AND created_at<?",(week_start.isoformat(),week_end.isoformat())).fetchone()[0]
            current_run = db.execute("SELECT r.input_hash FROM customers c JOIN runs r ON c.run_id=r.id LIMIT 1").fetchone()
            demo_path = root/"data/scoring/active_customers.csv"
            demo_scoring = bool(current_run and demo_path.exists() and current_run[0] == file_hash(demo_path))
            return jsonify(analysis=analysis,evaluation=evaluation,config=config,customers=customers,tasks=queue(db),
                runs=runs,outcomes=outcomes,statuses=STATUSES,outcome_options=OUTCOMES,
                now=now.isoformat(),simulation=True,weekly_created=weekly_created,demo_scoring=demo_scoring,
                validation=json.loads((root/"reports/validation.json").read_text()))
        finally: db.close()

    @app.post("/api/pipeline")
    def pipeline():
        return jsonify(run_pipeline(root=root))

    @app.post("/api/pipeline/upload")
    def upload():
        file = request.files.get("file")
        if not file or not file.filename.lower().endswith(".csv"): raise ValueError("Choose a CSV scoring input (maximum 5 MB).")
        dest = root/"var/uploads"/(uuid.uuid4().hex+".csv")
        dest.parent.mkdir(parents=True,exist_ok=True)
        file.save(dest)
        return jsonify(run_pipeline(dest,root=root))

    @app.patch("/api/tasks/<int:task_id>")
    def edit(task_id):
        data = request.get_json() or {}
        db = connect(root/"var/retention.sqlite")
        try: update_task(db,task_id,data.get("status"),data.get("owner"),data.get("updated_at"))
        finally: db.close()
        return jsonify(ok=True)

    @app.post("/api/tasks/<int:task_id>/outcome")
    def outcome(task_id):
        data = request.get_json() or {}
        db = connect(root/"var/retention.sqlite")
        try: record_outcome(db,task_id,data.get("result"),data.get("notes",""),data.get("observed_at"),data.get("followup_date"))
        finally: db.close()
        return jsonify(ok=True)

    @app.get("/api/tasks/<int:task_id>/audit")
    def audit(task_id):
        db = connect(root/"var/retention.sqlite")
        try: return jsonify(rows(db,"SELECT * FROM audit WHERE task_id=? ORDER BY id DESC",(task_id,)))
        finally: db.close()

    @app.get("/api/export/queue.csv")
    def export():
        db = connect(root/"var/retention.sqlite")
        try: content = queue_csv(queue(db))
        finally: db.close()
        return Response(content,mimetype="text/csv",headers={"Content-Disposition":"attachment; filename=retention-queue.csv"})

    @app.get("/api/export/scoring-template.csv")
    def scoring_template():
        return Response((root/"data/scoring/active_customers.csv").read_text(),mimetype="text/csv",headers={"Content-Disposition":"attachment; filename=active-customers-demo.csv"})

    @app.errorhandler(Exception)
    def error(exc):
        if isinstance(exc,HTTPException): return jsonify(error=exc.description),exc.code
        if isinstance(exc,(ValueError,LookupError)): return jsonify(error=str(exc)),400 if isinstance(exc,ValueError) else 404
        app.logger.exception("Request failed")
        return jsonify(error="The operation failed. Your last successful results are preserved. Review pipeline history or the server log."),500
    return app
