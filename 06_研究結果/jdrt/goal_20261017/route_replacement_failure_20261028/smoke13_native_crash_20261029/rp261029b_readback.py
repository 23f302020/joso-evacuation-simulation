"""Read current-production six-probe raw frames; no adoption or READY output."""
from pathlib import Path
from datetime import datetime
import hashlib
import json
import math
import sys
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / '04_プログラム'))
from scripts.jdrt_choice_toolchain import resolve_choice_toolchain, load_choice_traci, choice_runtime_fingerprint

read = lambda p: json.loads(p.read_bytes())
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
cfg = read(ROOT / '04_プログラム/config/jdrt_realtime_choice_v1.json')
workspace = ROOT / cfg['workspace']
tool = resolve_choice_toolchain(require_manifest=True)
fingerprint = choice_runtime_fingerprint(tool, load_choice_traci(tool))
variants = ['production_past_stop_index', 'production_past_stop_moving', 'production_past_stop_loop',
            'native_past_stop_future', 'production_future_closed', 'stopped_cancel']
report = {'at_jst': datetime.now().astimezone().isoformat(), 'original_session': 60531,
          'original_exit_code': 0, 'source_sha256': sha(Path(__file__)), 'runs': [],
          'research_adoption_permitted': False, 'technical_ready': False,
          'scope': 'Six artificial current-production route-history probes, not full registered settings',
          'limitations': ['No debugger memory-address trace of private stop-index vector',
                          'Raw collision/teleport getters were enforced by collector; no independent missing native getter reconstruction']}
for i, variant in enumerate(variants, 1):
    folder = workspace / 'technical' / f'rp261029b{i}'
    m = read(folder / 'manifest.json')
    assert m['status'] == 'COMPLETED' and m['variant'] == variant
    assert m['research_adoption_permitted'] is m['core_adoption_permitted'] is False
    assert 'diagnostic_native_override' not in m and m['runtime_sha256'] == fingerprint
    for path, expected in m['source_sha256'].items():
        assert sha(ROOT / path) == expected
    assert Path(m['command'][0]) == Path(tool['sumo'])
    assert all(m['checks'].values())
    frames = read(folder / 'frames.json')
    step = float(m['command'][m['command'].index('--step-length') + 1])
    speed = float(ET.parse(folder / 'types.xml').getroot().find('vType').get('maxSpeed'))
    assert [f['time_sec'] for f in frames] == [(j + 1) * step for j in range(len(frames))]
    residual = 0.
    for before, after in zip(frames, frames[1:]):
        assert all(math.isfinite(f[k]) for f in (before, after)
                   for k in ('time_sec', 'position', 'distance', 'speed'))
        dt = after['time_sec'] - before['time_sec']
        delta = after['distance'] - before['distance']
        assert -1e-6 <= delta <= speed * dt + 1e-6
        residual = max(residual, delta - speed * dt)
    before = m['before']
    assert before == read(folder / 'before_control.json')['before']
    assert before in frames and before['road'] == 'c'
    assert before['route_index'] == max(j for j, edge in enumerate(before['route']) if edge == 'c')
    if i <= 4:
        assert before['route_index'] >= sum(x.startswith('history_') for x in before['route'])
        after, final, first = m['immediate_after'], m['final_native'], m['first_valid_reentry']
        assert m['native_error'] is None and after['route'] == ['c', 'd'] and after['route_index'] == 0
        assert after['time_sec'] == before['time_sec'] and after['distance'] == before['distance']
        assert first in frames and first['road'] == 'c' and 0 < first['time_sec'] - before['time_sec'] <= step
        assert -1e-6 <= first['position'] - before['position'] <= speed * step + 1e-6
        assert final == frames[-1] and final['road'] == 'd' and final['stopped']
    elif variant == 'production_future_closed':
        assert m['native_error'] and "No connection between edge 'c' and edge 'd'" in (folder / 'sumo_errors.log').read_text()
    else:
        assert m['immediate_after'] == before and m['final_native'] == frames[-1]
        assert frames[-1]['stopped'] and frames[-1]['distance'] == before['distance']
    if variant == 'production_past_stop_loop':
        assert before['route_index'] > m['first_loop_stop']['route_index']
        assert {'loop_out', 'loop_back'} <= {f['road'] for f in frames}
    report['runs'].append({'run_id': m['run_id'], 'variant': variant, 'frames': len(frames),
                           'before_route_index': before['route_index'],
                           'max_distance_step_upper_bound_residual_m': residual,
                           'artifacts': {str(p.relative_to(ROOT)): sha(p) for p in folder.iterdir() if p.is_file()}})
report['status'] = 'SIX_CURRENT_PRODUCTION_RAW_READBACK_CHECKED_NOT_READY'
out = Path(__file__).with_name('rp261029b_independent_readback.json')
with out.open('x', encoding='utf-8') as stream:
    json.dump(report, stream, ensure_ascii=False, indent=2, allow_nan=False)
print(json.dumps({'status': report['status'], 'runs': len(report['runs']),
                  'frames': sum(x['frames'] for x in report['runs']),
                  'artifacts': sum(len(x['artifacts']) for x in report['runs'])}))
