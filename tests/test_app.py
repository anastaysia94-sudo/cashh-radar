import os, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
TEST_DB=Path('/tmp/cashh_radar_test.db')
if TEST_DB.exists(): TEST_DB.unlink()
os.environ['CASHH_DB_PATH']=str(TEST_DB)
os.environ['CASHH_ADMIN_EMAIL']='admin@example.com'
os.environ['CASHH_ADMIN_PASSWORD']='AdminPassword123!'
os.environ['CASHH_SECRET_KEY']='test-secret-not-production'
os.environ['CASHH_DEV_MODE']='1'

from fastapi.testclient import TestClient
import app

client=TestClient(app.app)

def csrf(c):
    r=c.get('/api/me'); assert r.status_code==200; return r.json().get('csrf_token','')

def test_health_and_opportunities():
    assert client.get('/api/health').json()['status']=='ok'
    data=client.get('/api/opportunities').json()
    assert data['count'] >= 6
    assert all('verification' in x for x in data['opportunities'])

def test_user_execution_flow():
    c=TestClient(app.app)
    r=c.post('/api/register',json={'email':'user@example.com','password':'StrongPassword123!'})
    assert r.status_code==200
    token=r.json()['csrf_token']; headers={'X-CSRF-Token':token}
    r=c.put('/api/profile',headers=headers,json={'goal':'remote income with no startup cost','work_mode':'remote','startup_budget':0,'urgency_days':14,'experience':'entry','location':''})
    assert r.status_code==200
    opps=c.get('/api/opportunities').json()['opportunities']; oid=opps[0]['id']
    assert c.post(f'/api/watchlist/{oid}',headers=headers).status_code==200
    assert len(c.get('/api/watchlist').json()['opportunities'])==1
    assert c.post('/api/roadmaps',headers=headers,json={'opportunity_id':oid}).status_code==200
    assert c.post('/api/outreach',headers=headers,json={'opportunity_id':oid,'asset_type':'application_email'}).status_code==200
    assert c.post('/api/alerts',headers=headers,json={'name':'Deadline watch','kind':'deadline','days':30,'enabled':True}).status_code==200
    assert c.post('/api/alerts/evaluate',headers=headers).status_code==200
    assert c.post('/api/outcomes',headers=headers,json={'opportunity_id':oid,'stage':'started','notes':'test','amount':None}).status_code==200
    assert c.post('/api/advisor',json={'goal':'remote entry level','work_mode':'remote','startup_budget':0,'urgency_days':14,'experience':'entry','limit':3}).status_code==200
    assert len(c.get('/api/outcomes').json()['outcomes'])==1

def test_admin_flow():
    c=TestClient(app.app)
    r=c.post('/api/login',json={'email':'admin@example.com','password':'AdminPassword123!'})
    assert r.status_code==200
    headers={'X-CSRF-Token':r.json()['csrf_token']}
    dash=c.get('/api/admin/dashboard'); assert dash.status_code==200
    opps=c.get('/api/admin/opportunities').json()['opportunities']
    source=next(x for x in opps if x['trust']!='demo')
    assert c.post(f"/api/admin/opportunities/{source['id']}/verify",headers=headers).status_code==200
    checked=c.get(f"/api/opportunities/{source['id']}").json()['opportunity']
    assert checked['verification']['status']=='verified'

def test_plans_and_seo():
    assert set(client.get('/api/plans').json()['plans'])=={'free','pro','team'}
    assert client.get('/robots.txt').status_code==200
    assert client.get('/sitemap.xml').status_code==200
    assert client.get('/manifest.json').json()['name']=='Cashh Radar'
