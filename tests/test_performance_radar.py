import sqlite3

from cashh_performance_radar import segment_learning


def make_conn():
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row
    conn.executescript(
        '''
        CREATE TABLE prospect_catalog(
          prospect_id TEXT PRIMARY KEY,
          industry TEXT
        );
        CREATE TABLE prospect_user_state(
          user_id INTEGER NOT NULL,
          prospect_id TEXT NOT NULL,
          sent_at TEXT,
          replied_at TEXT,
          outcome_stage TEXT,
          outcome_amount REAL,
          minutes_spent INTEGER NOT NULL DEFAULT 0
        );
        '''
    )
    return conn


def add(conn, user_id, prospect_id, industry, sent=True, replied=False, paid=False, amount=0, minutes=0):
    conn.execute('INSERT INTO prospect_catalog(prospect_id,industry) VALUES(?,?)', (prospect_id, industry))
    conn.execute(
        'INSERT INTO prospect_user_state VALUES(?,?,?,?,?,?,?)',
        (
            user_id,
            prospect_id,
            '2026-09-13T01:00:00+00:00' if sent else None,
            '2026-09-13T02:00:00+00:00' if replied else None,
            'paid' if paid else None,
            amount if paid else None,
            minutes,
        ),
    )


def test_segment_adjustment_is_zero_below_minimum_sample():
    conn = make_conn()
    add(conn, 1, 'a', 'Bakery', replied=True, paid=True, amount=100, minutes=30)
    add(conn, 1, 'b', 'Bakery', replied=True, paid=True, amount=100, minutes=30)
    learned = segment_learning(conn, 1)['Bakery']
    assert learned['sent_count'] == 2
    assert learned['score_adjustment'] == 0.0
    assert learned['confidence'] == 'insufficient_sample'
    assert learned['sample_weight'] == 0.0


def test_segment_learning_rewards_observed_outperformance_and_penalizes_underperformance():
    conn = make_conn()
    for i in range(5):
        add(conn, 1, f's{i}', 'Strong', replied=i < 4, paid=i < 2, amount=100 if i < 2 else 0, minutes=30)
    for i in range(5):
        add(conn, 1, f'w{i}', 'Weak', replied=False, paid=False, minutes=30)

    learned = segment_learning(conn, 1)
    strong = learned['Strong']
    weak = learned['Weak']
    assert strong['sent_count'] == 5
    assert strong['score_adjustment'] > 0
    assert weak['score_adjustment'] < 0
    assert strong['confidence'] == 'growing'
    assert weak['confidence'] == 'growing'
    assert strong['sample_weight'] == 0.5
    assert strong['actual_revenue'] == 200.0
    assert strong['realized_hourly'] == 80.0
    assert abs(strong['score_adjustment']) <= 10
    assert abs(weak['score_adjustment']) <= 10


def test_learning_is_user_scoped_and_reaches_full_weight_at_ten_sends():
    conn = make_conn()
    for i in range(10):
        add(conn, 1, f'u1-{i}', 'Retail', replied=i < 5, paid=i < 2, amount=100 if i < 2 else 0, minutes=20)
    for i in range(10):
        add(conn, 2, f'u2-{i}', 'Retail', replied=True, paid=True, amount=1000, minutes=1)
    learned = segment_learning(conn, 1)['Retail']
    assert learned['sent_count'] == 10
    assert learned['replied_count'] == 5
    assert learned['paid_count'] == 2
    assert learned['actual_revenue'] == 200.0
    assert learned['confidence'] == 'full'
    assert learned['sample_weight'] == 1.0
