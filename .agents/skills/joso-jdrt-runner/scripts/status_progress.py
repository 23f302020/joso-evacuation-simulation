"""Reflect only the dated progress region from the status Markdown to HTML."""
import argparse
import json
from pathlib import Path

from realtime_choice_cell import reflect_progress, single_writer


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--check', action='store_true')
    mode.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[4]
    base = root / '00_全体整理/現状把握_静的・動的シミュレーション整理'
    parameters = json.loads((root / '04_プログラム/config/jdrt_realtime_choice_v1.json').read_text(encoding='utf-8'))
    with single_writer(root / parameters['workspace']):
        markdown = base.with_suffix('.md').read_text(encoding='utf-8')
        target = base.with_suffix('.html')
        with target.open(encoding='utf-8', newline='') as stream:
            before = stream.read()
        after = reflect_progress(markdown, before)
        if args.check:
            print('PASS: dated progress agrees' if before == after else 'STALE: run with --apply')
            return 0 if before == after else 1
        temporary = target.with_name(target.name + '.progress.tmp')
        with temporary.open('x', encoding='utf-8', newline='') as stream:
            stream.write(after)
        try:
            temporary.replace(target)
        finally:
            if temporary.exists():
                temporary.unlink()
        print('Updated dated progress from Markdown')
        return 0


if __name__ == '__main__':
    raise SystemExit(main())
