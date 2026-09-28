import json
from retention.web import create_app
from retention.pipeline import run_pipeline

def test_local_api_and_mutation_protection(isolated,now):
    run_pipeline(root=isolated,now=now)
    app=create_app(isolated);app.config['TESTING']=True
    client=app.test_client()
    assert client.get('/').status_code==200
    assert client.get('/api/health').json['simulation'] is True
    dash=client.get('/api/dashboard').json
    assert len(dash['customers'])==1035 and len(dash['tasks'])==100 and not dash['outcomes']
    assert client.post('/api/pipeline').status_code==403
    with client.session_transaction() as session:csrf=session['csrf']
    t=dash['tasks'][0]
    r=client.patch(f"/api/tasks/{t['id']}",json={'status':'Assigned','owner':'Test queue','updated_at':t['updated_at']},headers={'X-CSRF-Token':csrf})
    assert r.status_code==200
    assert client.get(f"/api/tasks/{t['id']}/audit").json[0]['event']=='workflow_updated'
    csv=client.get('/api/export/queue.csv')
    assert csv.status_code==200 and b'Test queue' in csv.data
    assert client.get('/api/dashboard',headers={'Host':'untrusted.example'}).status_code==400
