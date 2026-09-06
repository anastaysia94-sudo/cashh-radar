from fastapi.testclient import TestClient
import app


def auth_client(email, password):
    c=TestClient(app.app)
    r=c.post('/api/register',json={'email':email,'password':password})
    assert r.status_code==200
    return c,r.json()['csrf_token']


def test_pulse_saved_search_and_export():
    c,token=auth_client('pulse@example.com','StrongPassword123!')
    h={'X-CSRF-Token':token}
    r=c.post('/api/saved-searches',headers=h,json={'name':'Remote','text':'remote','min_match':0})
    assert r.status_code==200
    assert len(c.get('/api/saved-searches').json()['saved_searches'])==1
    pulse=c.get('/api/pulse'); assert pulse.status_code==200; assert 'saved_search_matches' in pulse.json()
    digest=c.get('/api/digest'); assert digest.status_code==200; assert 'top_matches' in digest.json()
    export=c.get('/api/account/export'); assert export.status_code==200; assert export.json()['account']['email']=='pulse@example.com'


def test_admin_api_enterprise_provider_layers():
    c=TestClient(app.app)
    r=c.post('/api/login',json={'email':'admin@example.com','password':'AdminPassword123!'})
    assert r.status_code==200
    token=r.json()['csrf_token']; h={'X-CSRF-Token':token}
    key=c.post('/api/api-keys',headers=h,json={'name':'CI key'}); assert key.status_code==200
    raw=key.json()['api_key']
    public=c.get('/api/v1/opportunities',headers={'X-API-Key':raw}); assert public.status_code==200; assert public.json()['count']>0
    org=c.post('/api/organizations',headers=h,json={'name':'Cashh Radar Labs','slug':'cashh-radar-labs'}); assert org.status_code==200
    provider=c.post('/api/admin/providers',headers=h,json={'name':'Example Provider','category':'Business Services','website':'https://example.com','disclosure':'Example test provider','status':'active'}); assert provider.status_code==200
    assert c.get('/api/providers').json()['providers']
    ops=c.get('/api/admin/operations'); assert ops.status_code==200; assert 'duplicates' in ops.json()


def test_account_password_and_delete():
    c,token=auth_client('delete@example.com','StrongPassword123!'); h={'X-CSRF-Token':token}
    assert c.post('/api/account/password',headers=h,json={'current_password':'StrongPassword123!','new_password':'NewStrongPassword123!'}).status_code==200
    assert c.request('DELETE','/api/account',headers=h,json={'password':'NewStrongPassword123!','confirmation':'DELETE'}).status_code==200
    assert c.get('/api/me').json()['authenticated'] is False

def test_password_reset_dev_flow():
    c,token=auth_client('reset@example.com','StrongPassword123!')
    r=c.post('/api/account/password-reset/request',json={'email':'reset@example.com'})
    assert r.status_code==200 and r.json().get('dev_reset_token')
    raw=r.json()['dev_reset_token']
    r=c.post('/api/account/password-reset/confirm',json={'token':raw,'new_password':'ResetPassword123!'})
    assert r.status_code==200
    assert c.post('/api/login',json={'email':'reset@example.com','password':'ResetPassword123!'}).status_code==200


def login_admin():
    c=TestClient(app.app)
    r=c.post('/api/login',json={'email':'admin@example.com','password':'AdminPassword123!'})
    assert r.status_code==200
    return c,r.json()['csrf_token']


def test_referral_signup_attribution():
    ref,token=auth_client('referrer@example.com','StrongPassword123!')
    code=ref.get('/api/referral').json()['code']
    referred=TestClient(app.app)
    r=referred.post('/api/register',json={'email':'referred@example.com','password':'StrongPassword123!','referral_code':code})
    assert r.status_code==200
    events=ref.get('/api/referral').json()['events']
    assert events.get('signup')==1


def test_team_invite_membership_and_org_api_key():
    admin,token=login_admin();h={'X-CSRF-Token':token}
    org=admin.post('/api/organizations',headers=h,json={'name':'Enterprise Ops','slug':'enterprise-ops'});assert org.status_code==200
    oid=org.json()['organization_id']
    member,mtoken=auth_client('orgmember@example.com','StrongPassword123!')
    inv=admin.post(f'/api/organizations/{oid}/invites',headers=h,json={'email':'orgmember@example.com','role':'analyst'})
    assert inv.status_code==200
    raw=inv.json()['invite_url'].split('org_invite=',1)[1]
    accepted=member.post('/api/organizations/invites/accept',headers={'X-CSRF-Token':mtoken},json={'token':raw})
    assert accepted.status_code==200 and accepted.json()['role']=='analyst'
    members=admin.get(f'/api/organizations/{oid}/members').json()['members']
    assert any(x['email']=='orgmember@example.com' and x['role']=='analyst' for x in members)
    branded=admin.put(f'/api/organizations/{oid}/branding',headers=h,json={'brand_name':'Enterprise Radar','accent_color':'#00E5C2','logo_url':None,'custom_domain':'radar.example.com'})
    assert branded.status_code==200
    key=admin.post('/api/api-keys',headers=h,json={'name':'Org key','organization_id':oid,'scopes':['opportunities:read']})
    assert key.status_code==200 and key.json()['rate_limit_per_minute']==300
    public=admin.get('/api/v1/opportunities',headers={'X-API-Key':key.json()['api_key']})
    assert public.status_code==200 and public.json()['tenant']['brand_name']=='Enterprise Radar'


def test_provider_lead_pipeline():
    admin,token=login_admin();h={'X-CSRF-Token':token}
    pr=admin.post('/api/admin/providers',headers=h,json={'name':'Pipeline Provider','category':'Business Services','website':'https://example.org','disclosure':'Test only','status':'active'})
    assert pr.status_code==200;pid=pr.json()['id']
    user,utoken=auth_client('leaduser@example.com','StrongPassword123!');uh={'X-CSRF-Token':utoken}
    lead=user.post('/api/provider-leads',headers=uh,json={'provider_id':pid,'note':'Please introduce me'})
    assert lead.status_code==200;lid=lead.json()['lead_id']
    updated=admin.put(f'/api/admin/provider-leads/{lid}',headers=h,json={'status':'qualified','admin_note':'Evidence reviewed'})
    assert updated.status_code==200
    mine=user.get('/api/provider-leads').json()['provider_leads']
    assert mine[0]['status']=='qualified' and mine[0]['admin_note']=='Evidence reviewed'
    stats=admin.get('/api/admin/providers/analytics');assert stats.status_code==200


def test_background_jobs_metrics_and_readiness():
    admin,token=login_admin();h={'X-CSRF-Token':token}
    r=admin.post('/api/admin/jobs/maintenance/run',headers=h);assert r.status_code==200 and r.json()['status']=='ok'
    jobs=admin.get('/api/admin/jobs').json()['jobs'];assert jobs and jobs[0]['job_name']=='maintenance'
    metrics=admin.get('/api/metrics');assert metrics.status_code==200 and 'cashh_users_total' in metrics.text
    health=admin.get('/api/health').json();assert health['schema_version']>=2 and health['version']=='2.2.0'
    ready=admin.get('/api/health/ready');assert ready.status_code==200
