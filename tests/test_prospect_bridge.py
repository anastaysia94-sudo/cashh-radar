import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

TEST_DB = Path('/tmp/cashh_radar_prospect_bridge_test.db')
if TEST_DB.exists():
    TEST_DB.unlink()
os.environ['CASHH_DB_PATH'] = str(TEST_DB)
os.environ['CASHH_SECRET_KEY'] = 'prospect-bridge-test-secret'
os.environ['CASHH_DEV_MODE'] = '1'
os.environ['CASHH_SCHEDULER_ENABLED'] = '0'

from fastapi.testclient import TestClient
import app as core
from cashh_loop import register_cashh_loop
from cashh_prospect_bridge import register_prospect_bridge

register_cashh_loop(core.app)
register_prospect_bridge(core.app)


def register_user(email='bridge-user@example.com'):
    c = TestClient(core.app)
    response = c.post('/api/register', json={'email': email, 'password': 'StrongPassword123!'})
    assert response.status_code == 200, response.text
    return c, {'X-CSRF-Token': response.json()['csrf_token']}


def test_bundle_becomes_normal_cashh_radar_opportunities():
    client = TestClient(core.app)
    status = client.get('/api/prospects/status')
    assert status.status_code == 200
    payload = status.json()
    assert payload['bridge'] == 'unified'
    assert payload['catalog']['total'] == 500
    assert payload['bundle_sync']['total'] == 500

    opportunities = client.get('/api/opportunities?category=Client%20Prospect').json()
    assert opportunities['count'] == 500
    sample = opportunities['opportunities'][0]
    assert sample['source_key'] == 'prospect_engine'
    assert sample['income_label'] == 'Proposed offer value (not guaranteed income)'
    assert sample['evidence']['offer_value']['classification'] == 'financial_model_assumption'


def test_prospect_state_persists_and_advances_canonical_loop():
    c, headers = register_user()
    queue = c.get('/api/prospects/queue?limit=1')
    assert queue.status_code == 200
    item = queue.json()['items'][0]
    prospect_id = item['prospect']['prospect_id']
    opportunity_id = item['prospect']['opportunity_id']

    sent_at = '2026-09-12T18:00:00+00:00'
    sent = c.put(
        f'/api/prospects/state/{prospect_id}',
        headers=headers,
        json={
            'status': 'SENT',
            'verified': True,
            'sent_at': sent_at,
            'last_contact_type': 'INIT',
            'minutes_spent': 15,
            'event_type': 'sent',
        },
    )
    assert sent.status_code == 200, sent.text
    assert sent.json()['pipeline']['stage'] == 'acted'

    replied = c.put(
        f'/api/prospects/state/{prospect_id}',
        headers=headers,
        json={
            'status': 'REPLIED',
            'verified': True,
            'sent_at': sent_at,
            'replied_at': '2026-09-12T20:00:00+00:00',
            'minutes_spent': 30,
            'notes': 'Asked for the exact deliverables.',
            'event_type': 'reply',
        },
    )
    assert replied.status_code == 200, replied.text
    assert replied.json()['pipeline']['stage'] == 'responded'

    paid = c.put(
        f'/api/prospects/state/{prospect_id}',
        headers=headers,
        json={
            'status': 'WON / PAID',
            'verified': True,
            'sent_at': sent_at,
            'replied_at': '2026-09-12T20:00:00+00:00',
            'outcome_stage': 'paid',
            'outcome_amount': 100,
            'minutes_spent': 60,
            'notes': 'Actual test payment outcome.',
            'event_type': 'paid',
        },
    )
    assert paid.status_code == 200, paid.text
    body = paid.json()
    assert body['pipeline']['stage'] == 'learned'
    assert body['ranking']['hourly']['kind'] == 'realized'
    assert body['ranking']['hourly']['value'] == 100.0

    detail = c.get(f'/api/loop/{opportunity_id}')
    assert detail.status_code == 200
    stages = [row['stage'] for row in detail.json()['outcomes']]
    assert 'contacted' in stages
    assert 'replied' in stages
    assert 'paid' in stages

    # Repeating the identical paid state must not duplicate the paid outcome.
    again = c.put(
        f'/api/prospects/state/{prospect_id}',
        headers=headers,
        json={
            'status': 'WON / PAID',
            'outcome_stage': 'paid',
            'outcome_amount': 100,
            'minutes_spent': 60,
            'event_type': 'sync',
        },
    )
    assert again.status_code == 200
    detail2 = c.get(f'/api/loop/{opportunity_id}').json()
    assert [row['stage'] for row in detail2['outcomes']].count('paid') == 1

    state = c.get('/api/prospects/state').json()['states']
    row = next(x for x in state if x['prospect_id'] == prospect_id)
    assert row['status'] == 'WON / PAID'
    assert row['minutes_spent'] == 60
    assert row['outcome_amount'] == 100


def test_unified_radar_contains_sales_and_non_sales_opportunities():
    c, _ = register_user('radar-user@example.com')
    radar = c.get('/api/radar/unified?limit=200')
    assert radar.status_code == 200
    body = radar.json()
    assert body['client_prospects'] > 0
    assert body['other_money_opportunities'] > 0
    families = {item['source_family'] for item in body['items']}
    assert 'client_prospect' in families
    assert 'money_opportunity' in families
    prospect = next(item for item in body['items'] if item['source_family'] == 'client_prospect')
    assert prospect['hourly']['kind'] in {'modeled_offer_value', 'realized'}
    assert 'not guaranteed' in body['ranking_note'].lower() or 'assumptions' in body['ranking_note'].lower()


def test_bridge_registration_is_idempotent():
    register_prospect_bridge(core.app)
    paths = [route.path for route in core.app.routes]
    assert paths.count('/api/prospects/state/{prospect_id}') == 1
    assert paths.count('/api/radar/unified') == 1
