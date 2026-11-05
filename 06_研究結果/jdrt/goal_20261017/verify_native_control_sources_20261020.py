"""Verify prepared control source bytes as a separately observable child."""
import argparse
import hashlib
import json
import os
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--snapshot', type=Path, required=True)
parser.add_argument('--source-root', type=Path, required=True)
args = parser.parse_args()
snapshot = json.loads(args.snapshot.read_bytes())
if snapshot['status'] != 'PREPARED_NOT_BUILT':
    raise ValueError('Source preparation is incomplete')
root = args.source_root.resolve(strict=True)
if os.name == 'nt':
    root = Path('\\\\?\\' + str(root))
expected = snapshot['source_sha256']['control']
actual = {}
for path in root.rglob('*'):
    if path.is_symlink() or path.is_junction():
        raise ValueError('Source tree link found')
    if path.is_file():
        with path.open('rb') as stream:
            actual[path.relative_to(root).as_posix()] = hashlib.file_digest(stream, 'sha256').hexdigest()
if actual != expected:
    differences = sorted(name for name in set(actual) | set(expected) if actual.get(name) != expected.get(name))
    raise ValueError('Control source inventory changed: ' + repr(differences))
print(json.dumps({'status': 'SOURCE_BYTES_MATCH_PREPARED_SNAPSHOT', 'file_count': len(actual),
                  'snapshot_sha256': hashlib.sha256(args.snapshot.read_bytes()).hexdigest(),
                  'simulation_executed': False}, ensure_ascii=False))
