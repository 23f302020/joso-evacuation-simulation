"""Read-only source reconciliation; optional extraction of a reference CSV, never run inputs."""
from pathlib import Path
import argparse
import csv
import hashlib
import json
import re
from datetime import datetime, timezone, timedelta

import pdfplumber
from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / '02_情報調査/交通・地域/jdrt_realistic'
CSV = BASE / '既存9施設_公表容量照合_20261015.csv'
PDF = BASE / 'sources_shelters/joso_plan_appendix_r8_202604.pdf'
FROZEN = ROOT / '04_プログラム/output/sumo/regions/08211/derived/shelters_sumo.csv'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    with path.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--extract-reference', action='store_true')
    args = parser.parse_args()
    hashes, failures, unacquired = {}, [], []
    manifests = [
        ('sources_behavior/metadata.json', 'sources_behavior'),
        ('sources_transport/metadata_20261015.json', 'sources_transport'),
        ('sources_shelters/fetch_metadata.json', None),
        ('追加取得記録_20261015.json', None),
    ]
    for manifest, subdir in manifests:
        obj = json.loads((BASE / manifest).read_text(encoding='utf-8'))
        records = obj['sources'] if isinstance(obj, dict) else obj
        for item in records:
            if not item.get('sha256'):
                unacquired.append({'manifest': manifest, 'url': item['url'],
                                   'status': item.get('http_status'), 'error': item.get('error')})
                continue
            path = BASE / subdir / item['file'] if subdir else ROOT / item.get('raw_path', item.get('file', ''))
            actual = sha(path)
            hashes[path.relative_to(ROOT).as_posix()] = actual
            if actual != item['sha256']:
                failures.append(f'SHA mismatch: {path}')
    with pdfplumber.open(PDF) as doc:
        table = doc.pages[49].extract_tables()[0][1:]
    lookup = {r[1].replace(' ', ''): r for r in table}
    frozen = rows(FROZEN)
    records = []
    text = PdfReader(PDF).pages[49].extract_text()
    for source in frozen:
        name = source['name']
        record = lookup[name]
        # Independent text engine: verify the name/phone/capacity row without table geometry.
        match = re.search(re.escape(name) + r'\s+(.+?)\s+(\d{2}-\d{4})\s+(\d+)\s', text)
        if not match or int(match.group(3)) != int(record[4]):
            failures.append('PDF text/table disagreement: ' + name)
        if record[6]:
            failures.append('Unexpected remark for frozen destination: ' + name)
        records.append({
            'shelter_id': source['shelter_id'], 'name': name,
            'published_capacity_people': int(record[4]),
            'source_address': record[2],
            'address_conflict': 'true' if name == '飯沼小学校' else 'false',
            'capacity_status': 'published_candidate', 'open_from_sec': '',
            'welfare_compatibility': 'unknown',
            'adoption_status': 'candidate_not_adopted',
            'source_url': 'https://www.city.joso.lg.jp/data/doc/1782889830_doc_28_0.pdf',
            'source_pdf_page': 50, 'source_printed_page': 47,
            'source_sha256': sha(PDF),
        })
    if args.extract_reference:
        if CSV.exists():
            raise RuntimeError('Reference exists; inspect before replacing it.')
        with CSV.open('w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=list(records[0]))
            writer.writeheader()
            writer.writerows(records)
    saved = rows(CSV)
    if saved != [{k: str(v) for k, v in r.items()} for r in records]:
        failures.append('Reference CSV differs from PDF extraction')
    if len({r['shelter_id'] for r in saved}) != len(frozen):
        failures.append('Shelter ID coverage/uniqueness')
    if any(r['capacity'] != '0' for r in frozen):
        failures.append('Frozen capacity changed from unknown sentinel')
    v2path = FROZEN.parent / 'agent_types.csv'
    r0path = FROZEN.parent.parent / 'experiments/scenario_c/inputs/ownership_sensitivity_20260826/non_car_15pct/scenario_c_agent_types.csv'
    a, b = rows(v2path), rows(r0path)
    by_origin = {r['origin_id']: r for r in b}
    comparison = {}
    for key in ['total_pop', 'elderly_pop', 'type3_no_car_non_elderly_pop', 'type4_no_car_elderly_pop']:
        comparison[key] = {'v2': sum(int(r[key]) for r in a),
                           'r0': sum(int(r[key]) for r in b),
                           'different_origins': sum(int(r[key]) != int(by_origin[r['origin_id']][key]) for r in a)}
    for path in [PDF, FROZEN, CSV, v2path, r0path]:
        hashes[path.relative_to(ROOT).as_posix()] = sha(path)
    out = {
        'verified_at_jst': datetime.now(timezone(timedelta(hours=9))).isoformat(),
        'scope': 'source SHA, shelter reference extraction by two PDF engines, preserved input comparison; no formal adoption',
        'status': 'PASS' if not failures else 'FAIL', 'failures': failures,
        'source_hashes': hashes, 'unacquired_sources': unacquired,
        'shelter_count': len(saved),
        'capacity_sum_people': sum(int(r['published_capacity_people']) for r in saved),
        'adopted_input_changes': False,
        'population_comparison': comparison,
    }
    destination = Path(__file__).with_name('現実条件根拠検証_20261015.json')
    destination.write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in out.items() if k != 'source_hashes'}, ensure_ascii=False, indent=2))
    if failures:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
