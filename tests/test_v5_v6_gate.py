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


def test_shared_directory_source_is_not_treated_as_shared_business_domain(tmp_path):
    history = tmp_path / 'history.csv'
    candidates = tmp_path / 'candidates.csv'
    out = tmp_path / 'out'
    write_csv(history, [
        {
            'Business': 'Historical Co',
            'Known Public Email(s)': 'old@historical.example',
            'Known Website Domain(s)': 'historical.example',
        }
    ])
    directory = 'https://public.example.gov/current-qualified-contractors.pdf'
    write_csv(candidates, [
        {'Business': 'Fresh Electric', 'Email': 'estimating@fresh-electric.example', 'City': 'San Jose', 'Industry': 'Electrical', 'Observation': 'Current qualified contractor; C-10 electrical', 'SourceURL': directory},
        {'Business': 'Fresh Plumbing', 'Email': 'office@fresh-plumbing.example', 'City': 'Campbell', 'Industry': 'Plumbing', 'Observation': 'Current qualified contractor; C-36 plumbing', 'SourceURL': directory},
    ])
    report = run(history, candidates, out)
    assert report['accepted_rows'] == 2
    accepted = list(csv.DictReader(open(out / 'accepted.csv', encoding='utf-8-sig')))
    assert {row['_normalized_domain'] for row in accepted} == {'fresh-electric.example', 'fresh-plumbing.example'}
    assert report['historical_unique_domains'] == 1


def test_gate_checks_all_historical_email_and_domain_values(tmp_path):
    history = tmp_path / 'history.csv'
    candidates = tmp_path / 'candidates.csv'
    out = tmp_path / 'out'
    write_csv(history, [
        {
            'Business': 'Legacy Builder',
            'Known Public Email(s)': 'first@legacy.example; second@legacy.example',
            'Known Website Domain(s)': 'old-legacy.example; legacy.example',
        }
    ])
    write_csv(candidates, [
        {'Business': 'Renamed Operation', 'Email': 'second@legacy.example', 'City': 'San Jose', 'Industry': 'Construction', 'Observation': 'Current general-building work', 'SourceURL': 'https://directory.example/one'},
        {'Business': 'Another Renamed Operation', 'Email': 'new@legacy.example', 'Website': 'https://legacy.example', 'City': 'Santa Clara', 'Industry': 'Construction', 'Observation': 'Current general-building work', 'SourceURL': 'https://directory.example/two'},
    ])
    report = run(history, candidates, out)
    assert report['accepted_rows'] == 0
    rejected = list(csv.DictReader(open(out / 'rejected.csv', encoding='utf-8-sig')))
    assert any('historical_email_match' in row['_reasons'] for row in rejected)
    assert any('historical_domain_match' in row['_reasons'] for row in rejected)
    assert report['historical_unique_emails'] == 2
    assert report['historical_unique_domains'] == 2
