"""Prepare only the explicitly publishable research-status HTML module."""
import argparse
import base64
import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parents[4]
source = root / '00_全体整理/現状把握_静的・動的シミュレーション整理.html'
directory = root / '00_全体整理/公開用_cloudflare'
data = source.read_bytes()
encoded = json.dumps(base64.b64encode(data).decode('ascii'))
module = '''const html = Uint8Array.from(atob(ENCODED), c => c.charCodeAt(0));
export default {
  async fetch(request) {
    const url = new URL(request.url);
    if (url.pathname === '/index.html') return Response.redirect(url.origin + '/', 308);
    if (url.pathname !== '/') return new Response('Not Found', { status: 404 });
    if (!['GET', 'HEAD'].includes(request.method)) return new Response('Method Not Allowed', {status: 405, headers: {Allow: 'GET, HEAD'}});
    return new Response(request.method === 'HEAD' ? null : html, {headers: {'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-cache'}});
  }
};
'''.replace('ENCODED', encoded).encode('utf-8')
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--check', action='store_true')
args = parser.parse_args()
targets = {directory / 'public/index.html': data, directory / 'status-worker.mjs': module}
for path, content in targets.items():
    if args.check:
        assert path.read_bytes() == content, f'Stale publication artifact: {path}'
    else:
        path.write_bytes(content)
print(json.dumps({'check': args.check, 'source_sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)}))
