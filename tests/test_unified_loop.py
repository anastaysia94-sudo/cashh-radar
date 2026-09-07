import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

TEST_DB = Path('/tmp/cashh_radar_unified_loop_test.db')
if TEST_DB.exists():
    TEST_DB.unlink()
os.environ['CASHH_DB_PATH'] = str(TEST_DB)
os.environ['CASHH_SECRET_KEY'] = 'unified-loop-test-secret'
os.environ['CASHH_DEV_MODE'] = '1'

from fastapi.testclient import TestClient
import app as core
from cashh_loop import register_cashh_loop

register_cashh_loop(core.app)
client = TestClient(core.app)


def test_unified_loop_end_to_end_and_learning():
    c = TestClient(core.app)
    registered = c.post(
        '/api/register',
        json={'email': 'loop-user@example.com', 'password': 'StrongPassword123!'},
    )
    assert registered.status_code == 200
    headers = {'X-CSRF-Token': registered.json()['csrf_token']}

    # Use a service-model opportunity so the auto action is a proposal.
    first = c.post(
        '/api/loop/run',
        headers=headers,
        json={'opportunity_id': 'demo-002', 'asset_type': 'auto', 'generate_action': True},
    )
    assert first.status_code == 200
    payload = first.json()
    assert payload['stage'] == 'action_ready'
    assert payload['verification']['status'] == 'illustrative'
    assert 0 <= payload['score'] <= 100
    assert payload['action']['kind'] == 'outreach'
    assert payload['action']['asset_type'] == 'proposal'
    assert payload['explanation']['learning']['relevant_samples'] == 0

    actioned = c.post(
        '/api/loop/demo-002/actioned',
        headers=headers,
        json={'channel': 'email', 'notes': 'Sent a truthful tailored proposal.'},
    )
    assert actioned.status_code == 200
    assert actioned.json()['stage'] == 'acted'

    replied = c.post(
        '/api/loop/demo-002/response',
        headers=headers,
        json={'response_type': 'reply', 'notes': 'Prospect replied with a scope question.'},
    )
    assert replied.status_code == 200
    assert replied.json()['stage'] == 'responded'
    assert replied.json()['mapped_outcome_stage'] == 'replied'

    paid = c.post(
        '/api/loop/demo-002/outcome',
        headers=headers,
        json={'stage': 'paid', 'notes': 'Paid test outcome.', 'amount': 100},
    )
    assert paid.status_code == 200
    assert paid.json()['stage'] == 'learned'
    assert paid.json()['effect'].startswith('This outcome is now part of the evidence')

    detail = c.get('/api/loop/demo-002')
    assert detail.status_code == 200
    detail_payload = detail.json()
    assert detail_payload['pipeline']['stage'] == 'learned'
    assert detail_payload['pipeline']['latest_outcome_stage'] == 'paid'
    assert [event['event_type'] for event in detail_payload['events']] == [
        'run', 'actioned', 'response', 'outcome', 'learned'
    ]

    # A subsequent opportunity with related history should receive a bounded
    # personalized learning signal rather than ignoring the recorded result.
    second = c.post(
        '/api/loop/run',
        headers=headers,
        json={'opportunity_id': 'demo-004', 'asset_type': 'auto', 'generate_action': True},
    )
    assert second.status_code == 200
    learned = second.json()['explanation']['learning']
    assert learned['relevant_samples'] >= 1
    assert 0 < learned['adjustment'] <= 10

    learning_summary = c.get('/api/loop-learning')
    assert learning_summary.status_code == 200
    assert learning_summary.json()['cap'] == 10


def test_loop_routes_are_registered_once():
    register_cashh_loop(core.app)
    paths = [route.path for route in core.app.routes]
    assert paths.count('/api/loop/run') == 1
    assert paths.count('/api/loop/{opportunity_id}/outcome') == 1
