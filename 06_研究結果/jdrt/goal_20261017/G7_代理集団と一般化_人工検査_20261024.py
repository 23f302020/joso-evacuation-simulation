"""Exact finite artificial checks for a set-average bound, not research results."""
from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path

root = Path.cwd()
goal = root / '06_研究結果/jdrt/goal_20261017'
rate_checks = effect_checks = sharp_pairs = 0
for n in (6,):
    universe = (1 << n) - 1
    for proxy in range(1, universe + 1):
        p = proxy.bit_count()
        for target in range(1, universe + 1):
            m = target.bit_count()
            k = (proxy & target).bit_count()
            upper = p * m - k * min(p, m)
            assert upper == max((p - k) * m, (m - k) * p)
            maximum = 0
            for admitted in range(universe + 1):
                difference = abs((proxy & admitted).bit_count() * m -
                                 (target & admitted).bit_count() * p)
                assert difference <= upper
                maximum = max(maximum, difference)
                rate_checks += 1
            assert maximum == upper
            sharp_pairs += 1
for n in (4,):
    universe = (1 << n) - 1
    for proxy in range(1, universe + 1):
        p = proxy.bit_count()
        for target in range(1, universe + 1):
            m = target.bit_count()
            k = (proxy & target).bit_count()
            upper = 2 * (p * m - k * min(p, m))
            for a in range(universe + 1):
                for b in range(universe + 1):
                    difference = abs(((proxy & a).bit_count() - (proxy & b).bit_count()) * m -
                                     ((target & a).bit_count() - (target & b).bit_count()) * p)
                    assert difference <= upper
                    effect_checks += 1
report = {'at_jst': datetime.now().astimezone().isoformat(),
          'status': 'ARTIFICIAL_FINITE_SET_BOUND_CHECKS_PASS',
          'rate_checks': rate_checks, 'sharp_set_pairs': sharp_pairs,
          'effect_checks': effect_checks, 'arithmetic': 'exact integer cross-products; no floating tolerance',
          'scope': 'all nonempty set pairs/all binary outcomes on artificial universes6 and4',
          'script_sha256': sha256(Path(__file__).read_bytes()).hexdigest(),
          'research_rows_used': 0, 'medical_membership_observed': False,
          'real_world_error_bound_estimated': False, 'new_metric_or_method_adopted': False,
          'limits': 'Common fixed per-person outcomes required; population/traffic changes and model-reality errors excluded'}
with (goal / 'G7_代理集団と一般化_人工検査_20261024.json').open('x', encoding='utf-8') as stream:
    json.dump(report, stream, ensure_ascii=False, indent=2)
    stream.write('\n')
print(json.dumps(report, ensure_ascii=False))
