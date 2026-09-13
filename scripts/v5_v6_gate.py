from __future__ import annotations

import argparse
import csv
import json
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

COMMON_COMPANY_TOKENS = {
    'inc', 'incorporated', 'llc', 'l l c', 'corp', 'corporation', 'co', 'company',
    'ltd', 'limited', 'dba', 'the', 'and', '&'
}

FREE_EMAIL_DOMAINS = {
    'gmail.com', 'yahoo.com', 'yahoo.net', 'outlook.com', 'hotmail.com', 'live.com',
    'aol.com', 'icloud.com', 'me.com', 'msn.com', 'proton.me', 'protonmail.com',
    'comcast.net', 'sbcglobal.net', 'earthlink.net', 'att.net'
}


def _clean(value: str | None) -> str:
    return (value or '').strip()


def normalize_email(value: str | None) -> str:
    return _clean(value).lower()


def normalize_phone(value: str | None) -> str:
    digits = re.sub(r'\D+', '', _clean(value))
    return digits[-10:] if len(digits) >= 10 else digits


def normalize_domain(value: str | None) -> str:
    raw = _clean(value).lower()
    if not raw:
        return ''
    if '@' in raw and '://' not in raw:
        raw = raw.rsplit('@', 1)[-1]
    if '://' not in raw:
        raw = 'https://' + raw
    try:
        host = (urlparse(raw).hostname or '').lower()
    except Exception:
        host = ''
    if host.startswith('www.'):
        host = host[4:]
    return host


def normalize_name(value: str | None) -> str:
    text = _clean(value).lower().replace('’', "'")
    text = re.sub(r'\bd/b/a\b', ' dba ', text)
    text = re.sub(r'[^a-z0-9]+', ' ', text)
    tokens = [t for t in text.split() if t not in COMMON_COMPANY_TOKENS]
    return ''.join(tokens)


def first_present(row: dict[str, str], *keys: str) -> str:
    lowered = {k.lower(): v for k, v in row.items()}
    for key in keys:
        if key in row and _clean(row[key]):
            return _clean(row[key])
        if key.lower() in lowered and _clean(lowered[key.lower()]):
            return _clean(lowered[key.lower()])
    return ''


def split_list_values(value: str | None) -> list[str]:
    raw = _clean(value)
    if not raw:
        return []
    return [part.strip() for part in re.split(r'[;|,\n]+', raw) if part.strip()]


def first_list_value(value: str | None) -> str:
    values = split_list_values(value)
    return values[0] if values else ''


def candidate_business_domain(row: dict[str, str], normalized_email: str) -> str:
    website = first_list_value(first_present(
        row,
        'Website', 'Domain', 'Known Website Domain(s)', 'Website Domain'
    ))
    if website:
        return normalize_domain(website)
    email_domain = normalize_domain(normalized_email)
    if email_domain and email_domain not in FREE_EMAIL_DOMAINS:
        return email_domain
    return ''


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline='', encoding='utf-8-sig') as fh:
        return list(csv.DictReader(fh))


@dataclass
class Decision:
    accepted: bool
    reasons: list[str]
    normalized_name: str
    normalized_email: str
    normalized_domain: str
    normalized_phone: str


def fingerprint(row: dict[str, str]) -> tuple[str, str, str, str]:
    name = first_present(row, 'Business', 'Business Name', 'Company', 'Name', 'Normalized Business')
    email = normalize_email(first_list_value(first_present(
        row,
        'Email', 'Public Email', 'Contact Email', 'Known Public Email(s)'
    )))
    domain = candidate_business_domain(row, email)
    phone = first_list_value(first_present(row, 'Phone', 'Phone #', 'Telephone', 'Known Phone(s)'))
    return (
        normalize_name(name),
        email,
        domain,
        normalize_phone(phone),
    )


def build_exclusion(rows: list[dict[str, str]]) -> dict[str, set[str]]:
    names, emails, domains, phones = set(), set(), set(), set()
    for row in rows:
        name = first_present(row, 'Business', 'Business Name', 'Company', 'Name', 'Normalized Business')
        if name:
            names.add(normalize_name(name))

        email_cell = first_present(row, 'Known Public Email(s)', 'Email', 'Public Email', 'Contact Email')
        for value in split_list_values(email_cell):
            normalized = normalize_email(value)
            if normalized:
                emails.add(normalized)

        domain_cell = first_present(row, 'Known Website Domain(s)', 'Website', 'Domain', 'Website Domain')
        for value in split_list_values(domain_cell):
            normalized = normalize_domain(value)
            if normalized:
                domains.add(normalized)

        phone_cell = first_present(row, 'Known Phone(s)', 'Phone', 'Phone #', 'Telephone')
        for value in split_list_values(phone_cell):
            normalized = normalize_phone(value)
            if normalized:
                phones.add(normalized)
    return {'name': names, 'email': emails, 'domain': domains, 'phone': phones}


def evaluate(row: dict[str, str], exclusion: dict[str, set[str]], accepted_so_far: dict[str, set[str]]) -> Decision:
    n, e, d, p = fingerprint(row)
    reasons: list[str] = []
    business = first_present(row, 'Business', 'Business Name', 'Company', 'Name')
    source = first_present(row, 'SourceURL', 'Source URL', 'Source')
    city = first_present(row, 'City', 'Location', 'Service Area')
    industry = first_present(row, 'Industry', 'Category', 'Service Focus')
    observation = first_present(row, 'Observation', 'CustomerObservation', 'Signal', 'Why Selected', 'WhyV5', 'WhyV6')

    if not business:
        reasons.append('missing_business_name')
    if not e:
        reasons.append('missing_public_email')
    if not source:
        reasons.append('missing_source_url')
    if not city:
        reasons.append('missing_city_or_service_area')
    if not industry:
        reasons.append('missing_industry_or_service_focus')
    if not observation:
        reasons.append('missing_personalization_observation')

    for kind, value in [('name', n), ('email', e), ('domain', d), ('phone', p)]:
        if value and value in exclusion[kind]:
            reasons.append(f'historical_{kind}_match')
        if value and value in accepted_so_far[kind]:
            reasons.append(f'in_batch_{kind}_duplicate')

    accepted = not reasons
    return Decision(accepted, reasons, n, e, d, p)


def run(history_csv: Path, candidate_csv: Path, out_dir: Path) -> dict[str, int]:
    history = load_csv(history_csv)
    candidates = load_csv(candidate_csv)
    exclusion = build_exclusion(history)
    seen = {k: set() for k in exclusion}
    accepted_rows, rejected_rows = [], []

    for row in candidates:
        decision = evaluate(row, exclusion, seen)
        enriched = dict(row)
        enriched.update({
            '_accepted': 'YES' if decision.accepted else 'NO',
            '_reasons': ';'.join(decision.reasons),
            '_normalized_name': decision.normalized_name,
            '_normalized_email': decision.normalized_email,
            '_normalized_domain': decision.normalized_domain,
            '_normalized_phone': decision.normalized_phone,
        })
        if decision.accepted:
            accepted_rows.append(enriched)
            for kind, value in [
                ('name', decision.normalized_name),
                ('email', decision.normalized_email),
                ('domain', decision.normalized_domain),
                ('phone', decision.normalized_phone),
            ]:
                if value:
                    seen[kind].add(value)
        else:
            rejected_rows.append(enriched)

    out_dir.mkdir(parents=True, exist_ok=True)
    all_fields = []
    for row in accepted_rows + rejected_rows:
        for key in row:
            if key not in all_fields:
                all_fields.append(key)

    def write_csv(path: Path, output_rows: list[dict[str, str]]) -> None:
        with path.open('w', newline='', encoding='utf-8-sig') as fh:
            writer = csv.DictWriter(fh, fieldnames=all_fields)
            writer.writeheader()
            writer.writerows(output_rows)

    write_csv(out_dir / 'accepted.csv', accepted_rows)
    write_csv(out_dir / 'rejected.csv', rejected_rows)

    report = {
        'historical_rows': len(history),
        'historical_unique_names': len(exclusion['name']),
        'historical_unique_emails': len(exclusion['email']),
        'historical_unique_domains': len(exclusion['domain']),
        'historical_unique_phones': len(exclusion['phone']),
        'candidate_rows': len(candidates),
        'accepted_rows': len(accepted_rows),
        'rejected_rows': len(rejected_rows),
    }
    (out_dir / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description='Gate V5/V6 candidates against the historical prospect universe.')
    parser.add_argument('--history-csv', type=Path, required=True)
    parser.add_argument('--candidates', type=Path, required=True)
    parser.add_argument('--out-dir', type=Path, required=True)
    args = parser.parse_args()
    report = run(args.history_csv, args.candidates, args.out_dir)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
