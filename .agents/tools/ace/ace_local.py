"""Offline ACE playbook adapter. Research executors are outside its write scope."""
import argparse
import contextlib
from datetime import datetime, timezone
import hashlib
import importlib
import io
import json
import os
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
HEADER = '## STRATEGIES & INSIGHTS\n\n## COMMON MISTAKES TO AVOID\n\n## OTHERS\n'
REVISION = '82709de050e1db6e6ef2f07bcb0393560b94992a'


def digest(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def validate_delta(delta, playbook, ledger):
    if not isinstance(delta, dict) or set(delta) != {'base_sha256', 'operations', 'bullet_tags'}:
        raise ValueError('Invalid delta fields')
    if delta['base_sha256'] != digest(playbook):
        raise ValueError('Stale playbook base')
    known_evidence = set(re.findall(r'^## (JD-\S+)', ledger, re.M))
    known_bullets = set(re.findall(r'^\[([^\]]+)\]', playbook, re.M))
    sections = set(re.findall(r'^## (.+)$', playbook, re.M))
    seen_tags = set()
    seen_content = set(re.findall(r'^\[[^\]]+\] helpful=\d+ harmful=\d+ :: (.+)$', playbook, re.M))
    for kind, fields in [('operations', {'type', 'section', 'content', 'evidence'}),
                         ('bullet_tags', {'id', 'tag', 'evidence'})]:
        items = delta[kind]
        if not isinstance(items, list) or len(items) > 20:
            raise ValueError('Delta must contain at most 20 items per kind')
        for item in items:
            if not isinstance(item, dict) or set(item) != fields:
                raise ValueError('Invalid item fields')
            evidence = item['evidence']
            if (not isinstance(evidence, list) or not evidence or len(evidence) > 20
                    or any(not isinstance(x, str) or x not in known_evidence for x in evidence)
                    or len(set(evidence)) != len(evidence)):
                raise ValueError('Evidence must refer to existing ledger headings')
            if kind == 'operations':
                text = item['content']
                if (item['type'] != 'ADD' or item['section'] not in sections
                        or not isinstance(text, str) or not 1 <= len(text.strip()) <= 2000
                        or any(ord(c) < 32 or c in '\u0085\u2028\u2029' for c in text)):
                    raise ValueError('Only single-line ADD operations in existing sections are allowed')
                rendered = text + ' [evidence: ' + ', '.join(evidence) + ']'
                if rendered in seen_content:
                    raise ValueError('Duplicate ADD content and evidence')
                seen_content.add(rendered)
            else:
                if (item['id'] not in known_bullets or item['id'] in seen_tags
                        or item['tag'] not in {'helpful', 'harmful', 'neutral'}):
                    raise ValueError('Unknown/duplicate bullet or invalid tag')
                seen_tags.add(item['id'])
    if not delta['operations'] and not delta['bullet_tags']:
        raise ValueError('Empty delta')


def read_state(directory):
    playbook, parent = HEADER, None
    files = sorted(directory.glob('[0-9]' * 6 + '.json'))
    for sequence, path in enumerate(files, 1):
        state = json.loads(path.read_text(encoding='utf-8'))
        if (path.name != f'{sequence:06d}.json' or state['sequence'] != sequence
                or state['parent_sha256'] != parent or state['revision'] != REVISION
                or state['playbook_sha256'] != digest(state['playbook'])):
            raise ValueError('Broken snapshot chain; preserve files and investigate')
        parent, playbook = hashlib.sha256(path.read_bytes()).hexdigest(), state['playbook']
    return playbook, parent, len(files)


def apply_delta(delta, directory, ledger, backend):
    directory.mkdir(parents=True, exist_ok=True)
    lock = directory / 'writer.lock'
    with lock.open('x', encoding='utf-8') as handle:
        handle.write(str(os.getpid()))
    try:
        playbook, parent, sequence = read_state(directory)
        validate_delta(delta, playbook, ledger)
        # Reapplying a tag with the same evidence must not inflate counters.
        prior_tags = set()
        for path in directory.glob('[0-9]' * 6 + '.json'):
            for tag in json.loads(path.read_text(encoding='utf-8'))['delta']['bullet_tags']:
                prior_tags.update((tag['id'], evidence) for evidence in tag['evidence'])
        if any((tag['id'], evidence) in prior_tags
               for tag in delta['bullet_tags'] for evidence in tag['evidence']):
            raise ValueError('This evidence has already been used to rate this bullet')
        operations = [{**op, 'content': op['content'] + ' [evidence: '
                       + ', '.join(op['evidence']) + ']'} for op in delta['operations']]
        with contextlib.redirect_stdout(io.StringIO()):
            playbook = backend.update_bullet_counts(playbook, delta['bullet_tags']) if delta['bullet_tags'] else playbook
            playbook, _ = backend.apply_curator_operations(
                playbook, operations, backend.get_next_global_id(playbook))
        state = {'sequence': sequence + 1, 'revision': REVISION,
                 'at_utc': datetime.now(timezone.utc).isoformat(), 'parent_sha256': parent,
                 'playbook': playbook, 'playbook_sha256': digest(playbook),
                 'ledger_sha256': digest(ledger), 'delta': delta}
        # Exclusive creation preserves all previous snapshots. A partial write fails closed on next read.
        with (directory / f'{sequence + 1:06d}.json').open('x', encoding='utf-8') as handle:
            json.dump(state, handle, ensure_ascii=False, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        return state
    finally:
        lock.unlink()


def offline_guard(event, args):
    if event in {'socket.connect', 'socket.getaddrinfo', 'socket.bind', 'subprocess.Popen', 'os.system'}:
        raise RuntimeError('ACE local adapter forbids network and process execution')


def load_backend():
    installation = json.loads((HERE / 'installation.json').read_text(encoding='utf-8'))
    if installation['revision'] != REVISION:
        raise ValueError('Unreviewed upstream revision')
    source = Path(installation['source'])
    for name, expected in installation['source_hashes'].items():
        if hashlib.sha256((source / name).read_bytes()).hexdigest() != expected:
            raise ValueError('Upstream source changed: ' + name)
    os.environ['PYTHON_DOTENV_DISABLED'] = '1'
    os.environ['TIKTOKEN_CACHE_DIR'] = installation['token_cache']
    sys.addaudithook(offline_guard)
    sys.path.insert(0, str(source))
    return importlib.import_module('playbook_utils')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['status', 'show', 'apply'])
    parser.add_argument('--delta', type=Path)
    args = parser.parse_args()
    directory = HERE / 'state'
    if args.command == 'apply':
        if args.delta is None or args.delta.stat().st_size > 100_000:
            parser.error('apply requires --delta JSON, at most 100KB')
        delta = json.loads(args.delta.read_text(encoding='utf-8'))
        ledger = (ROOT / '00_全体整理/判断と結果の台帳.md').read_text(encoding='utf-8')
        state = apply_delta(delta, directory, ledger, load_backend())
        print(json.dumps({'sequence': state['sequence'], 'playbook_sha256': state['playbook_sha256']}, ensure_ascii=False))
    else:
        playbook, _, count = read_state(directory)
        if args.command == 'show':
            print(playbook)
        else:
            print(json.dumps({'revision': REVISION, 'snapshots': count,
                              'playbook_sha256': digest(playbook), 'mode': 'local-no-api',
                              'external_llm': 'not configured or tested'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
