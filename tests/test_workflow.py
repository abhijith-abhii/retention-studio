from datetime import timedelta
import json
import numpy as np
import pytest
import yaml
from retention.pipeline import run_pipeline
from retention.playbook import load_config, recommendation, exclusion, band
from retention.paths import ROOT
from retention.store import connect, queue, update_task, record_outcome, queue_csv

def test_rules_use_verified_signals(scoring,now):
    c=load_config(ROOT/'config/playbook.yaml');r=scoring.iloc[0].copy();r['score']=.9
    r.tenure=2;assert recommendation(r,c)['rule_id']=='onboarding'
    r.tenure=20;r.PaymentMethod='Electronic check';r.MonthlyCharges=100
    rec=recommendation(r,c);assert rec['rule_id']=='billing'
    assert r.customerID in rec['draft'] and 'SIMULATION' in rec['draft']
    r.PaymentMethod='Mailed check';r.InternetService='DSL';r.TechSupport='No'
    assert recommendation(r,c)['rule_id']=='education'
    r.TechSupport='Yes';assert recommendation(r,c)['rule_id']=='plan_fit'
    assert band(.8,c)=='High' and band(.4,c)=='Medium' and band(.1,c)=='Low'

def test_exclusions_and_cooldown(scoring,now):
    c=load_config(ROOT/'config/playbook.yaml');r=scoring.iloc[0].copy();r['score']=.9
    assert exclusion(r,c,[],now) is None
    r.Active='No';assert exclusion(r,c,[],now)=='Inactive customer';r.Active='Yes'
    c['excluded_customers']=[r.customerID];assert exclusion(r,c,[],now)=='Excluded by playbook';c['excluded_customers']=[]
    r.tenure=np.nan;assert exclusion(r,c,[],now)=='Missing required playbook signal';r.tenure=10
    r.score=.1;assert exclusion(r,c,[],now)=='Below minimum score';r.score=.9
    h=[{'status':'New','updated_at':now.isoformat(),'contacted_at':None}]
    assert exclusion(r,c,h,now)=='Open task already exists'
    h[0]['status']='Completed'
    assert exclusion(r,c,h,now+timedelta(days=29))=='Contact cooldown'
    assert exclusion(r,c,h,now+timedelta(days=30)) is None

def test_pipeline_is_idempotent_and_capacity_global(isolated,now):
    first=run_pipeline(root=isolated,now=now)
    second=run_pipeline(root=isolated,now=now)
    assert first['created']==100 and second['created']==0 and second['status']=='Skipped'
    f=isolated/'data/scoring/active_customers.csv'
    import pandas as pd
    d=pd.read_csv(f);d.loc[0,'MonthlyCharges']+=.01;d.to_csv(f,index=False)
    third=run_pipeline(root=isolated,now=now+timedelta(hours=1))
    assert third['created']==0 and third['capacity_used_before_run']==100
    db=connect(isolated/'var/retention.sqlite')
    tasks=queue(db)
    assert len(tasks)==100 and len({t['customer_id'] for t in tasks})==100
    assert min(t['score'] for t in tasks)==first['operational_cutoff']
    assert all(t['priority']==(1 if t['risk_band']=='High' else 2) for t in tasks)
    assert (isolated/'var/runs'/first['run_id']/'notification-summary.txt').exists()
    db.close()

def test_failed_input_preserves_state_and_logs_error(isolated,now):
    run_pipeline(root=isolated,now=now)
    db=connect(isolated/'var/retention.sqlite');before=db.execute('SELECT COUNT(*) FROM customers').fetchone()[0];db.close()
    invalid=isolated/'bad.csv';invalid.write_text('customerID\nbroken\n')
    with pytest.raises(ValueError):run_pipeline(invalid,root=isolated,now=now+timedelta(minutes=1))
    db=connect(isolated/'var/retention.sqlite')
    assert db.execute('SELECT COUNT(*) FROM customers').fetchone()[0]==before
    assert db.execute("SELECT COUNT(*) FROM runs WHERE status='Failed'").fetchone()[0]==1
    assert len(queue(db))==100;db.close()

def test_persistence_status_audit_and_outcomes(isolated,now):
    run_pipeline(root=isolated,now=now);db=connect(isolated/'var/retention.sqlite');t=queue(db)[0]
    update_task(db,t['id'],'Assigned','QA owner',t['updated_at'],now+timedelta(minutes=1));db.close()
    db=connect(isolated/'var/retention.sqlite');saved=db.execute('SELECT * FROM tasks WHERE id=?',(t['id'],)).fetchone()
    assert saved['status']=='Assigned' and saved['owner']=='QA owner'
    with pytest.raises(ValueError):update_task(db,t['id'],'Completed','Other',t['updated_at'])
    update_task(db,t['id'],'Completed','QA owner',saved['updated_at'],now+timedelta(minutes=2))
    with pytest.raises(ValueError):update_task(db,t['id'],'New','QA owner')
    record_outcome(db,t['id'],'No response','Intentional test only','2026-09-14','2026-09-21',now+timedelta(minutes=3))
    assert db.execute('SELECT simulation FROM outcomes').fetchone()[0]==1
    assert db.execute('SELECT COUNT(*) FROM audit WHERE task_id=?',(t['id'],)).fetchone()[0]==4
    with pytest.raises(ValueError):record_outcome(db,t['id'],'Retained at follow-up','','2030-01-01',None,now)
    db.close()

def test_zero_capacity_and_disabled_simulation(isolated,now):
    p=isolated/'config/playbook.yaml';c=yaml.safe_load(p.read_text());c['weekly_capacity']=0;p.write_text(yaml.safe_dump(c))
    assert run_pipeline(root=isolated,now=now)['created']==0
    c['simulation_only']=False;p.write_text(yaml.safe_dump(c))
    with pytest.raises(ValueError,match='simulation'):load_config(p)

def test_csv_formula_escaping():
    text=queue_csv([{'customer_id':'DEMO','owner':'=1+1'}])
    assert "'=1+1" in text

def test_concurrent_replays_create_one_batch(isolated,now):
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda _:run_pipeline(root=isolated,now=now),range(2)))
    assert sorted(r['status'] for r in results)==['Skipped','Success']
    db=connect(isolated/'var/retention.sqlite')
    assert len(queue(db))==100
    db.close()

def test_export_failure_rolls_back_new_snapshot(isolated,now,monkeypatch):
    from pathlib import Path
    import pandas as pd
    run_pipeline(root=isolated,now=now)
    db=connect(isolated/'var/retention.sqlite')
    old_snapshot=[tuple(r) for r in db.execute('SELECT * FROM customers ORDER BY customer_id')]
    db.close()
    f=isolated/'data/scoring/active_customers.csv';d=pd.read_csv(f);d.loc[0,'MonthlyCharges']+=1;d.to_csv(f,index=False)
    original=Path.write_text
    def fail_notification(self,*args,**kwargs):
        if self.name=='notification-summary.txt':raise OSError('Simulated disk failure')
        return original(self,*args,**kwargs)
    monkeypatch.setattr(Path,'write_text',fail_notification)
    with pytest.raises(OSError):run_pipeline(root=isolated,now=now+timedelta(days=7))
    db=connect(isolated/'var/retention.sqlite')
    assert len(queue(db))==100
    assert [tuple(r) for r in db.execute('SELECT * FROM customers ORDER BY customer_id')]==old_snapshot
    assert db.execute("SELECT COUNT(*) FROM runs WHERE status='Failed'").fetchone()[0]==1
    db.close()
