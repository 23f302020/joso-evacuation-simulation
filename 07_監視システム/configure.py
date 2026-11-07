"""Create machine-local paths without editing research parameters."""
import argparse
from pathlib import Path

from watch import BASE, ROOT, atomic_json, read_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--codex-exe', type=Path)
    parser.add_argument('--no-ai', action='store_true',
                        help='no AI diagnostics: no Codex path or model is written, diagnostics_enabled=false')
    parser.add_argument('--native-root', action='append', default=[], type=Path)
    args = parser.parse_args()
    if args.no_ai == (args.codex_exe is not None):
        parser.error('give exactly one of --no-ai or --codex-exe')
    if args.codex_exe is not None and not args.codex_exe.is_file():
        parser.error('Codex executable missing')
    destination = BASE / 'config.json'
    if destination.exists():
        parser.error('config.json already exists; inspect/edit it instead of replacing it')
    registry = read_json(ROOT / '04_プログラム/config/jdrt_realtime_choice_v1.json')
    workspace = ROOT / registry['workspace']
    # Avoid packaged-app LocalAppData virtualization and OneDrive synchronization.
    runtime = Path.home() / '.jdrt-monitor'
    import hashlib
    runtime /= hashlib.sha256(str(ROOT).encode()).hexdigest()[:12]
    patterns = [str(workspace / p) for p in ('runs/*/manifest.json', 'smoke/*/manifest.json',
                                           'technical/*/manifest.json', 'technical/*/execution/manifest.json')]
    for native in args.native_root:
        patterns.extend([str(native.resolve() / 'build_state.json'), str(native.resolve() / '*/build_state.json')])
    config = {'schema': 'simulation_watch_config_v1', 'runtime': str(runtime),
              'pythonw_exe': str(ROOT / '04_プログラム/venv/Scripts/pythonw.exe'),
              'patterns': patterns, 'sample_sec': 10, 'stale_sec': 600}
    if args.no_ai:
        config['diagnostics_enabled'] = False
    else:
        config.update(diagnostics_enabled=True, codex_exe=str(args.codex_exe.resolve()),
                      model='gpt-6-luna', diagnostic_timeout_sec=180, max_diagnostics_per_hour=3)
    atomic_json(destination, config)
    print(destination)


if __name__ == '__main__':
    main()
