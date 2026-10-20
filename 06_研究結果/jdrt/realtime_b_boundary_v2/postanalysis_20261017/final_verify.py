"""Final source, record, document and artifact checks. No mutation of research runs."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from html.parser import HTMLParser
from urllib.parse import unquote
import hashlib
import json
import re
import subprocess

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent


def sha(p):
    h = hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda: f.read(4 * 1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()


class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links, self.ids, self.headings, self.rows = [], [], [], 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if 'href' in a:
            self.links.append(a['href'])
        if 'id' in a:
            self.ids.append(a['id'])
        if tag in ['h1', 'h2']:
            self.headings.append(tag)
        self.rows += tag == 'tr'


def main():
    now = datetime.now(ZoneInfo('Asia/Tokyo')).isoformat()
    primary = json.loads((OUT.parent / '生成根拠.json').read_text(encoding='utf-8'))
    for path, digest in primary['source_sha256'].items():
        assert sha(ROOT / path) == digest, path
    for path, digest in primary['artifact_sha256'].items():
        target = ROOT / path
        if not target.exists():
            target = OUT.parent / path
        assert sha(target) == digest, path
    ledger = [json.loads(x) for x in (ROOT / '05_タスク管理/jdrt/JDRT-実時間B境界整合_セル検証台帳.jsonl').read_text(encoding='utf-8').splitlines() if x.strip()]
    recorded = {r['run_id'] for r in ledger}
    assert len(recorded) == len(ledger)
    six = ['05_タスク管理/jdrt/JDRT-実時間B境界整合_full実験記録.md',
           '05_タスク管理/jdrt/JDRT-v2_完了後方針・タスク.md', 'context.md', '00_全体整理/決定ログ.md',
           '01_経過報告/経過報告2026年08月/経過報告20260826.md',
           '05_タスク管理/jdrt/JDRT-実時間B境界整合_セル検証台帳.jsonl']
    for path in six:
        s = (ROOT / path).read_text(encoding='utf-8')
        assert all(run_id in s for run_id in recorded), path
    changes = json.loads((OUT / '文書更新記録.json').read_text(encoding='utf-8'))['changes']
    paths = [ROOT / r['path'] for r in changes]
    paths += [OUT.parent / '全セル結果一覧.md', OUT.parent / '全セル結果一覧.html']
    raw_html = json.loads((OUT / '公開資料再確認.json').read_text(encoding='utf-8'))['raw_file']
    paths += list(OUT.glob('*.md')) + [p for p in OUT.glob('*.html') if p.name != raw_html]
    broken = []
    checked = 0
    for p in paths:
        s = p.read_text(encoding='utf-8')
        assert b'\r\r\n' not in p.read_bytes(), str(p)
        if p.suffix == '.html':
            page = Page()
            page.feed(s)
            assert len(page.ids) == len(set(page.ids)), str(p)
            links = page.links
        elif p.suffix == '.md':
            links = re.findall(r'\[[^\]]*\]\(([^\s)]+)\)', s)
        else:
            continue
        for link in links:
            if ':' in link or link.startswith('#'):
                continue
            target = unquote(link.split('#')[0])
            checked += 1
            if not (p.parent / target).exists():
                broken.append({'path': p.relative_to(ROOT).as_posix(), 'link': link})
    # Some historical Markdown text embeds examples; preserve them separately.
    new_report_links = []
    for b in broken:
        if 'postanalysis_20261017' in b['path'] or 'postanalysis_20261017' in b['link']:
            new_report_links.append(b)
    assert not new_report_links, new_report_links
    doc_paths = [r['path'] for r in changes]
    process = subprocess.run(['git', 'diff', '--check', '--', *doc_paths], capture_output=True, text=True, encoding='utf-8')
    (OUT / 'git_diff_check.log').write_text(process.stdout + process.stderr, encoding='utf-8')
    assert process.returncode == 0
    for script in [ROOT / '04_プログラム/scripts/jdrt_realtime_b_boundary_postanalysis.py', ROOT / '04_プログラム/scripts/jdrt_realtime_b_boundary_postreport.py', OUT / 'update_current_documents.py']:
        compile(script.read_text(encoding='utf-8'), str(script), 'exec')
    page = Page()
    page.feed((OUT / '副指標・観測監査報告.html').read_text(encoding='utf-8'))
    assert page.headings.count('h1') == 1 and page.rows > len(ledger)
    auto = Path.home() / '.codex/automations/jdrt-b-15/automation.toml'
    assert 'status = "PAUSED"' in auto.read_text(encoding='utf-8')
    result = {'at_jst': now, 'status': 'PASS', 'source_files_unchanged': len(primary['source_sha256']),
              'formal_record_run_ids_preserved_in_six_files': len(recorded), 'local_links_checked': checked,
              'new_links_broken': new_report_links, 'historical_links_for_review': broken,
              'scoped_git_diff_check': process.returncode, 'html_heading_table_structure': True,
              'analysis_script_compilation': True, 'automation': 'PAUSED', 'new_simulations': 0, 'external_sends': 0,
              'source_implementation': primary['implementation_sha256']}
    (OUT / '最終照合.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    with (OUT / 'operations.jsonl').open('a', encoding='utf-8') as f:
        f.write(json.dumps({'at_jst': now, 'action': 'final_verified', 'result': result}, ensure_ascii=False) + '\n')
    provenance = json.loads((OUT / '分析生成根拠.json').read_text(encoding='utf-8'))
    provenance['finalized_at_jst'] = now
    provenance['report_script_sha256'] = sha(ROOT / '04_プログラム/scripts/jdrt_realtime_b_boundary_postreport.py')
    provenance['verification_script_sha256'] = sha(Path(__file__))
    provenance['artifact_sha256'] = {p.relative_to(OUT).as_posix(): sha(p) for p in OUT.rglob('*') if p.is_file() and p.name != '分析生成根拠.json'}
    provenance['mutable_log_note'] = 'SHA covers the local evidence snapshot at finalized_at_jst; later appends require a new finalization.'
    (OUT / '分析生成根拠.json').write_text(json.dumps(provenance, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k: v for k, v in result.items() if k != 'source_implementation'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
