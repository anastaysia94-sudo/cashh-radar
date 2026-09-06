from fastapi.testclient import TestClient
import app


def register(email,password='StrongPassword123!'):
    c=TestClient(app.app)
    r=c.post('/api/register',json={'email':email,'password':password})
    assert r.status_code==200, r.text
    return c,r.json().get('csrf_token')


def admin():
    c=TestClient(app.app)
    r=c.post('/api/login',json={'email':'admin@example.com','password':'AdminPassword123!'})
    assert r.status_code==200,r.text
    return c,r.json()['csrf_token']


def test_free_save_limit_is_enforced():
    c,token=register('limit@example.com');h={'X-CSRF-Token':token}
    opps=c.get('/api/opportunities').json()['opportunities']
    assert len(opps)>=6
    for o in opps[:5]: assert c.post(f"/api/watchlist/{o['id']}",headers=h).status_code==200
    r=c.post(f"/api/watchlist/{opps[5]['id']}",headers=h)
    assert r.status_code==403


def test_referral_public_endpoint_cannot_spoof_conversion():
    c,token=register('refsecure@example.com')
    code=c.get('/api/referral').json()['code']
    assert c.post('/api/referral/event',json={'code':code,'event_type':'visit','metadata':{}}).status_code==200
    assert c.post('/api/referral/event',json={'code':code,'event_type':'conversion','metadata':{}}).status_code==403


def test_two_step_login_dev_flow():
    c,token=register('twostep@example.com');h={'X-CSRF-Token':token}
    with app.db() as conn: conn.execute("UPDATE users SET email_verified_at=? WHERE email=?",(app.now_iso(),'twostep@example.com'))
    r=c.put('/api/account/security/two-step',headers=h,json={'enabled':True,'password':'StrongPassword123!'})
    assert r.status_code==200,r.text
    c.post('/api/logout',headers=h)
    x=TestClient(app.app)
    r=x.post('/api/login',json={'email':'twostep@example.com','password':'StrongPassword123!'})
    assert r.status_code==200 and r.json().get('two_step_required')
    d=r.json();r=x.post('/api/login/two-step',json={'challenge_token':d['challenge_token'],'code':d['dev_code']})
    assert r.status_code==200 and r.json()['user']['email']=='twostep@example.com'


def test_email_verification_token_flow():
    c,token=register('verify@example.com')
    with app.db() as conn: conn.execute("UPDATE users SET email_verified_at=NULL WHERE email=?",('verify@example.com',))
    r=c.post('/api/account/email-verification/request',json={'email':'verify@example.com'})
    assert r.status_code==200 and r.json().get('dev_verification_token')
    r=c.post('/api/account/email-verification/confirm',json={'token':r.json()['dev_verification_token']})
    assert r.status_code==200
    assert c.get('/api/account/security').json()['email_verified'] is True


def test_org_shared_watchlist_owner_transfer_scim_and_account_guard():
    a,at=admin();ah={'X-CSRF-Token':at}
    org=a.post('/api/organizations',headers=ah,json={'name':'Launch Team','slug':'launch-team-v22'});assert org.status_code==200,org.text
    oid=org.json()['organization_id']
    m,mt=register('launchmember@example.com');mh={'X-CSRF-Token':mt}
    inv=a.post(f'/api/organizations/{oid}/invites',headers=ah,json={'email':'launchmember@example.com','role':'analyst'});assert inv.status_code==200,inv.text
    raw=inv.json()['invite_url'].split('org_invite=',1)[1]
    assert m.post('/api/organizations/invites/accept',headers=mh,json={'token':raw}).status_code==200
    opp=a.get('/api/opportunities').json()['opportunities'][0]
    assert a.post(f"/api/organizations/{oid}/watchlist/{opp['id']}",headers=ah).status_code==200
    assert a.get(f'/api/organizations/{oid}/watchlist').json()['opportunities'][0]['id']==opp['id']
    members=a.get(f'/api/organizations/{oid}/members').json()['members'];mid=next(x['user_id'] for x in members if x['email']=='launchmember@example.com')
    assert a.put(f'/api/organizations/{oid}/owner',headers=ah,json={'new_owner_user_id':mid}).status_code==200
    # previous owner no longer owns it, new owner account deletion is safely blocked
    r=m.request('DELETE','/api/account',headers=mh,json={'password':'StrongPassword123!','confirmation':'DELETE'})
    assert r.status_code==409
    sc=m.post(f'/api/organizations/{oid}/scim-tokens',headers=mh,json={'name':'Launch SCIM'});assert sc.status_code==200,sc.text
    token=sc.json()['token']
    r=m.post('/scim/v2/Users',headers={'Authorization':f'Bearer {token}'},json={'userName':'scimuser@example.com','active':True,'roles':[{'value':'member'}]})
    assert r.status_code==201,r.text
    listing=m.get('/scim/v2/Users',headers={'Authorization':f'Bearer {token}'});assert listing.status_code==200 and listing.json()['totalResults']>=2


def test_commercial_api_scopes_and_backup_job():
    a,token=admin();h={'X-CSRF-Token':token}
    k=a.post('/api/api-keys',headers=h,json={'name':'All scopes','scopes':['opportunities:read','watchlists:read','alerts:read','analytics:read','usage:read']});assert k.status_code==200,k.text
    raw=k.json()['api_key'];kh={'X-API-Key':raw}
    for path in ['/api/v1/opportunities','/api/v1/watchlist','/api/v1/alerts','/api/v1/analytics','/api/v1/usage']:
        r=a.get(path,headers=kh);assert r.status_code==200,(path,r.text)
    b=a.post('/api/admin/jobs/backups/run',headers=h);assert b.status_code==200,b.text
    assert b.json()['verified'] is True

def test_launch_policy_and_support_pages_are_live():
    c=TestClient(app.app)
    for path,needle in [('/privacy','Privacy Policy'),('/terms','Terms of Use'),('/disclosures','Opportunity & Compensation Disclosures'),('/security','Security'),('/support','Support')]:
        r=c.get(path)
        assert r.status_code==200,(path,r.text)
        assert needle in r.text
    sitemap=c.get('/sitemap.xml').text
    assert '/privacy' in sitemap and '/support' in sitemap and '/security' in sitemap

def test_stripe_subscription_lifecycle_and_idempotency(monkeypatch):
    import json, time, hmac, hashlib
    monkeypatch.setenv('STRIPE_WEBHOOK_SECRET','whsec_test_launch')
    c,token=register('billinglife@example.com')
    with app.db() as conn:
        uid=conn.execute("SELECT id FROM users WHERE email=?",('billinglife@example.com',)).fetchone()['id']
    def send(event):
        raw=json.dumps(event,separators=(',',':')).encode();ts=str(int(time.time()))
        sig=hmac.new(b'whsec_test_launch',f'{ts}.'.encode()+raw,hashlib.sha256).hexdigest()
        return c.post('/api/billing/webhook',content=raw,headers={'stripe-signature':f't={ts},v1={sig}','content-type':'application/json'})
    completed={'id':'evt_launch_checkout','type':'checkout.session.completed','data':{'object':{'customer':'cus_launch','subscription':'sub_launch','metadata':{'user_id':str(uid),'plan':'pro'}}}}
    r=send(completed);assert r.status_code==200,r.text
    assert send(completed).json().get('duplicate') is True
    assert c.get('/api/me').json()['user']['plan']=='pro'
    class PortalResponse:
        ok=True
        def json(self): return {'url':'https://billing.stripe.test/session'}
    monkeypatch.setenv('STRIPE_SECRET_KEY','sk_test_launch')
    monkeypatch.setattr(app.requests,'post',lambda *args,**kwargs: PortalResponse())
    pr=c.post('/api/billing/portal',headers={'X-CSRF-Token':token});assert pr.status_code==200 and pr.json()['url'].startswith('https://billing.stripe.test/')
    deleted={'id':'evt_launch_deleted','type':'customer.subscription.deleted','data':{'object':{'id':'sub_launch','customer':'cus_launch','status':'canceled','metadata':{'user_id':str(uid),'plan':'pro'}}}}
    r=send(deleted);assert r.status_code==200,r.text
    me=c.get('/api/me').json()['user'];assert me['plan']=='free' and me['subscription_status']=='canceled'
