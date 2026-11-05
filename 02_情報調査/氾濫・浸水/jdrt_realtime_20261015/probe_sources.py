"""Preserve public primary sources for realtime-input assessment. Not a simulation runner."""
from pathlib import Path
import datetime
import hashlib
import json
import time
import urllib.request
import subprocess

BASE = Path(__file__).resolve().parent
RAW = BASE / 'raw'


def fetch(name, url):
    RAW.mkdir(exist_ok=True)
    dest = RAW / name
    meta = RAW / (name + '.metadata.json')
    if dest.exists() or meta.exists():
        raise RuntimeError('Do not overwrite acquired source: ' + name)
    stamp = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).isoformat()
    record = {'name': name, 'url': url, 'retrieved_at_jst': stamp,
              'scope': 'public-source read only; no parameter adoption'}
    try:
        with urllib.request.urlopen(url, timeout=40) as response:
            data = response.read()
            record.update(http_status=response.status, final_url=response.geturl(),
                          content_type=response.headers.get('Content-Type'),
                          sha256=hashlib.sha256(data).hexdigest(), size_bytes=len(data))
        dest.write_bytes(data)
    except Exception as exc:
        record.update(error=repr(exc))
    meta.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(record, ensure_ascii=False), flush=True)
    return record


def fetch_curl(name, url):
    """Use Windows certificate-verified TLS when Python's TLS backend is incompatible."""
    RAW.mkdir(exist_ok=True)
    dest = RAW / name
    meta = RAW / (name + '.metadata.json')
    if dest.exists() or meta.exists():
        raise RuntimeError('Do not overwrite acquired source: ' + name)
    stamp = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).isoformat()
    result = subprocess.run(
        ['curl.exe', '--fail', '--location', '--silent', '--show-error', '--max-time', '25',
         '--output', str(dest), '--write-out', '%{http_code}', url],
        capture_output=True, text=True,
    )
    record = {'name': name, 'url': url, 'retrieved_at_jst': stamp,
              'method': 'curl Schannel default certificate verification; no TLS bypass',
              'exit_code': result.returncode, 'http_status': result.stdout, 'error': result.stderr}
    if dest.exists():
        record.update(sha256=hashlib.sha256(dest.read_bytes()).hexdigest(),
                      size_bytes=dest.stat().st_size)
    meta.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(record, ensure_ascii=False), flush=True)
    return record


if __name__ == '__main__':
    sources = [
        ('gsi_2015_landing.html', 'https://www.gsi.go.jp/BOUSAI/H27.taihuu18gou.html'),
        ('suiboumap_api_manual_v3_2.pdf', 'https://suiboumap.gsi.go.jp/pdf/Data-riyo_manual.pdf'),
        ('shimodate_simulation_landing.html', 'https://www.ktr.mlit.go.jp/shimodate/shimodate00241.html'),
        ('breakpoints_probe.json', 'https://suiboumap.gsi.go.jp/shinsuimap/Api/Public/GetBreakPoint?lon=139.9890625&lat=36.10729166666667'),
    ]
    for name, url in sources:
        fetch(name, url)
        # Public API guide requests no more than about 30 requests/minute.
        time.sleep(2.1)
