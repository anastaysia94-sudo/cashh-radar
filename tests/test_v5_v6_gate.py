import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.v5_v6_gate import normalize_domain, normalize_name, normalize_phone, run


def write_csv(path, rows):
    fields = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with open(path, 'w', newline='', encoding='utf-8') as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def test_normalizers():
    assert normalize_name('Acme Construction, Inc.') == 'acmeconstruction'
    assert normalize_name('The Acme Construction LLC') == 'acmeconstruction'
    assert normalize_domain('https://www.Example.com/contact/') == 'example.com'
    assert normalize_domain('Hello@Example.com') == 'example.com'
    assert normalize_phone('(408) 555-1212') == '4085551212'


def test_gate_rejects_historical_and_in_batch_duplicates(tmp_path):
    history = tmp_path / 'history.csv'
    candidates = tmp_path / 'candidates.csv'
    out = tmp_path / 'out'
    write_csv(history, [
        {'Business': 'Acme Construction Inc', 'Email': 'info@acme.com', 'Website': 'https://acme.com', 'Phone': '408-555-1111'}
    ])
    write_csv(candidates, [
        {'Business': 'Acme Construction LLC', 'Email': 'new@newco.com', 'Website': 'https://newco.com', 'City': 'San Jose', 'Industry': 'Construction', 'Observation': 'Public page lists remodel work', 'SourceURL': 'https://source/1'},
        {'Business': 'Bright Electric', 'Email': 'hello@bright.com', 'Website': 'https://bright.com', 'City': 'Campbell', 'Industry': 'Electrical', 'Observation': 'EV charger services', 'SourceURL': 'https://source/2'},
        {'Business': 'Bright Electric Duplicate', 'Email': 'HELLO@BRIGHT.COM', 'Website': 'https://other.com', 'City': 'Campbell', 'Industry': 'Electrical', 'Observation': 'panel upgrades', 'SourceURL': 'https://source/3'},
    ])
    report = run(history, candidates, out)
    assert report['accepted_rows'] == 1
    assert report['rejected_rows'] == 2
    accepted = list(csv.DictReader(open(out / 'accepted.csv', encoding='utf-8-sig')))
    rejected = list(csv.DictReader(open(out / 'rejected.csv', encoding='utf-8-sig')))
    assert accepted[0]['Business'] == 'Bright Electric'
    assert any('historical_name_match' in row['_reasons'] for row in rejected)
    assert any('in_batch_email_duplicate' in row['_reasons'] for row in rejected)


def test_gate_requires_evidence_fields(tmp_path):
    history = tmp_path / 'history.csv'
    candidates = tmp_path / 'candidates.csv'
    out = tmp_path / 'out'
    write_csv(history, [{'Business': 'Old Co'}])
    write_csv(candidates, [{'Business': 'New Co', 'Email': 'info@new.co'}])
    report = run(history, candidates, out)
    assert report['accepted_rows'] == 0
    row = list(csv.DictReader(open(out / 'rejected.csv', encoding='utf-8-sig')))[0]
    assert 'missing_source_url' in row['_reasons']
    assert 'missing_city_or_service_area' in row['_reasons']
    assert 'missing_industry_or_service_focus' in row['_reasons']
    assert 'missing_personalization_observation' in row['_reasons']
