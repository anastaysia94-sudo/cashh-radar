import sqlite3

from prospect_performance import summarize


def make_conn():
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row
    conn.execute(
        '''
        CREATE TABLE prospect_user_state(
          user_id INTEGER NOT NULL,
          prospect_id TEXT NOT NULL,
          sent_at TEXT,
          replied_at TEXT,
          outcome_stage TEXT,
          outcome_amount REAL,
          minutes_spent INTEGER NOT NULL DEFAULT 0,
          updated_at TEXT NOT NULL
        )
        '''
    )
    return conn


def test_performance_counts_actual_paid_revenue_and_all_tracked_effort():
    conn = make_conn()
    conn.execute(
        'INSERT INTO prospect_user_state VALUES(?,?,?,?,?,?,?,?)',
        (1, 'paid-prospect', '2026-09-12T18:00:00+00:00', '2026-09-12T20:00:00+00:00', 'paid', 100, 60, '2026-09-12T21:00:00+00:00'),
    )
    first = summarize(conn, 1)
    assert first['sent_count'] == 1
    assert first['replied_count'] == 1
    assert first['paid_count'] == 1
    assert first['actual_revenue'] == 100.0
    assert first['tracked_minutes'] == 60
    assert first['reply_rate_pct'] == 100.0
    assert first['paid_rate_pct'] == 100.0
    assert first['realized_portfolio_hourly'] == 100.0

    # A second prospect consumed an hour but did not pay. That time belongs in the
    # denominator, while its proposed value must never appear as actual revenue.
    conn.execute(
        'INSERT INTO prospect_user_state VALUES(?,?,?,?,?,?,?,?)',
        (1, 'no-sale-prospect', '2026-09-12T22:00:00+00:00', None, None, 9999, 60, '2026-09-12T23:00:00+00:00'),
    )
    combined = summarize(conn, 1)
    assert combined['sent_count'] == 2
    assert combined['replied_count'] == 1
    assert combined['paid_count'] == 1
    assert combined['actual_revenue'] == 100.0
    assert combined['tracked_minutes'] == 120
    assert combined['reply_rate_pct'] == 50.0
    assert combined['paid_rate_pct'] == 50.0
    assert combined['realized_portfolio_hourly'] == 50.0
    assert combined['last_activity_at'] == '2026-09-12T23:00:00+00:00'
    assert 'proposed offers' in combined['basis'].lower()
    assert 'all tracked' in combined['basis'].lower()
    assert 'sent-outreach cohort' in combined['basis'].lower()


def test_performance_is_user_scoped_and_null_when_no_time_exists():
    conn = make_conn()
    conn.execute(
        'INSERT INTO prospect_user_state VALUES(?,?,?,?,?,?,?,?)',
        (2, 'someone-elses-paid-prospect', '2026-09-12T18:00:00+00:00', None, 'paid', 500, 30, '2026-09-12T19:00:00+00:00'),
    )
    result = summarize(conn, 1)
    assert result['sent_count'] == 0
    assert result['replied_count'] == 0
    assert result['paid_count'] == 0
    assert result['actual_revenue'] == 0.0
    assert result['tracked_minutes'] == 0
    assert result['reply_rate_pct'] is None
    assert result['paid_rate_pct'] is None
    assert result['realized_portfolio_hourly'] is None
    assert result['last_activity_at'] is None


def test_conversion_rates_ignore_orphan_reply_or_paid_records_without_sent_timestamp():
    conn = make_conn()
    conn.execute(
        'INSERT INTO prospect_user_state VALUES(?,?,?,?,?,?,?,?)',
        (1, 'imported-paid-without-send', None, '2026-09-12T20:00:00+00:00', 'paid', 100, 30, '2026-09-12T21:00:00+00:00'),
    )
    result = summarize(conn, 1)
    assert result['sent_count'] == 0
    assert result['replied_count'] == 0
    assert result['paid_count'] == 0
    assert result['reply_rate_pct'] is None
    assert result['paid_rate_pct'] is None
    # The payment remains real revenue and its tracked work still belongs in realized yield.
    assert result['actual_revenue'] == 100.0
    assert result['tracked_minutes'] == 30
    assert result['realized_portfolio_hourly'] == 200.0
