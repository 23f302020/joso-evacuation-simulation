"""Rebuild uncompressed source chronology and preserve original KML line geometry.

This does not infer flood depth, close roads, interpolate time, or run SUMO.
"""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import ast
import csv
import hashlib
import json
import re
import zipfile
import xml.etree.ElementTree as ET

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[2]
RAW = BASE / 'raw'
OUT = BASE / 'derived'


def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def dump(name, obj):
    p = OUT / name
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def main():
    OUT.mkdir(exist_ok=True)
    config_path = ROOT / '04_プログラム/scripts/config.py'
    tree = ast.parse(config_path.read_text(encoding='utf-8'))
    constants = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in ('SIM_START_EPOCH', 'KML_TIMESTAMPS'):
                    constants[target.id] = ast.literal_eval(node.value)
    tz = timezone(timedelta(hours=9))
    epoch = datetime.fromisoformat(constants['SIM_START_EPOCH']).replace(tzinfo=tz)
    archive = RAW / 'gsi_2015_joso_source.zip'
    old_archive = ROOT / '04_プログラム/data/flood_kml/D1-No917_joso.zip'
    features, chronology = [], []
    with zipfile.ZipFile(archive) as z:
        names = sorted(n for n in z.namelist() if n.lower().endswith('.kml'))
        for index, name in enumerate(names):
            suffix = re.search(r'(\d{12})\.kml$', name)
            if not suffix:
                raise ValueError('Cannot establish source time from filename: ' + name)
            date = datetime.strptime(suffix.group(1), '%Y%m%d%H%M').replace(tzinfo=tz)
            data = z.read(name)
            root = ET.fromstring(data)
            parents = {child: parent for parent in root.iter() for child in parent}
            count = 0
            for element in root.iter():
                if element.tag.rsplit('}', 1)[-1] != 'LineString':
                    continue
                coord = next((x for x in element.iter() if x.tag.rsplit('}', 1)[-1] == 'coordinates'), None)
                if coord is None or not coord.text:
                    raise ValueError('Source line without coordinates')
                coordinates = [[float(v) for v in token.split(',')[:2]] for token in coord.text.split()]
                if len(coordinates) < 2 or any(not (-180 <= c[0] <= 180 and -90 <= c[1] <= 90) for c in coordinates):
                    raise ValueError('Invalid geographic line')
                parent = element
                while parent in parents and parent.tag.rsplit('}', 1)[-1] != 'Placemark':
                    parent = parents[parent]
                label = next((e.text for e in parent if e.tag.rsplit('}', 1)[-1] == 'name'), None)
                style_url = next((e.text for e in parent if e.tag.rsplit('}', 1)[-1] == 'styleUrl'), None)
                source_colors = [e.text for e in parent.iter() if e.tag.rsplit('}', 1)[-1] == 'color']
                features.append({'type': 'Feature', 'geometry': {'type': 'LineString', 'coordinates': coordinates},
                                 'properties': {'source_member_suffix': suffix.group(0),
                                                'source_datetime_jst': date.isoformat(),
                                                'elapsed_from_reference_sec': (date - epoch).total_seconds(),
                                                'evidence_type': 'unclassified_source_line',
                                                'source_label': label, 'source_style_url': style_url,
                                                'source_inline_colors': source_colors,
                                                'role_classification': 'pending; may include boundary, breach, overflow, annotations',
                                                'depth_m': None, 'road_closure_time_sec': None,
                                                'member_sha256': hashlib.sha256(data).hexdigest()}})
                count += 1
            assigned = constants['KML_TIMESTAMPS'][index]
            chronology.append({'source_filename_timestamp': date.isoformat(),
                               'elapsed_from_reference_sec': int((date - epoch).total_seconds()),
                               'legacy_index_assigned_timestamp': assigned,
                               'timestamp_matches_legacy_index': date.replace(tzinfo=None).isoformat() == assigned,
                               'line_count': count,
                               'contains_polygon': any(e.tag.rsplit('}', 1)[-1] == 'Polygon' for e in root.iter()),
                               'member_sha256': hashlib.sha256(data).hexdigest()})
    hydro = json.loads((RAW / 'hydrograph_BP030_probe.json').read_text(encoding='utf-8'))
    if not isinstance(hydro, dict) or not hydro.get('data') or not hydro.get('bp'):
        raise ValueError('Hydrograph response is not source data')
    series = hydro['data']
    if any(a[0] >= b[0] for a, b in zip(series, series[1:])):
        raise ValueError('Hydrograph time is not strictly increasing')
    # API manual: series time is hours; info times are minutes. Keep both raw units.
    normalized = [{'elapsed_hours': t, 'elapsed_sec': t * 3600,
                   'depth_m': d, 'source_observation': 'official_hypothetical_simulation'} for t, d in series]
    crossings = []
    # The research legacy metre threshold is read from config without importing its side effects.
    depth_threshold = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
                           and any(isinstance(t, ast.Name) and t.id == 'FLOOD_DEPTH_THRESHOLD_M' for t in n.targets))
    for previous, current in zip(normalized, normalized[1:]):
        if previous['depth_m'] < depth_threshold <= current['depth_m']:
            crossings.append({'threshold_m': depth_threshold,
                              'time_lower_open_sec': previous['elapsed_sec'],
                              'time_upper_closed_sec': current['elapsed_sec'],
                              'uncertainty_interval_sec': current['elapsed_sec'] - previous['elapsed_sec'],
                              'interpolated_time_sec': None})
    mapping = ROOT / '04_プログラム/output/sumo/regions/08211/derived/time_mapping_sumo.csv'
    with mapping.open(encoding='utf-8-sig', newline='') as f:
        legacy_mapping = list(csv.DictReader(f))
    inputs = [archive, old_archive, config_path, mapping,
              RAW / 'hydrograph_BP030_probe.json', RAW / 'suiboumap_api_manual_schannel.pdf',
              ROOT / '04_プログラム/scripts/city_scenario.py',
              ROOT / '04_プログラム/scripts/p2_region_pipeline.py',
              ROOT / '04_プログラム/scripts/e1_load_flood_data.py']
    source_shas = {p.relative_to(ROOT).as_posix(): digest(p) for p in inputs}
    output = {
        'generated_at_jst': datetime.now(tz).isoformat(),
        'scope': 'uncompressed source chronology; reference geometry only, not simulation input',
        'reference_epoch_jst': epoch.isoformat(),
        'reference_epoch_role': 'legacy reference for audit; new evaluation-window choice not adopted',
        'source_zip_equals_preserved_legacy_zip': digest(archive) == digest(old_archive),
        'source_chronology': chronology,
        'legacy_mapping': legacy_mapping,
        'source_line_features': len(features),
        'source_timestamps_within_six_hours_after_reference': sum(0 <= r['elapsed_from_reference_sec'] <= 6 * 3600 for r in chronology),
        'old_index_timestamp_mismatch_count': sum(not r['timestamp_matches_legacy_index'] for r in chronology),
        'api_hypothetical_breakpoint': hydro['bp'],
        'api_raw_info_minutes': hydro['info'],
        'api_rising_threshold_intervals': crossings,
        'temporal_error_to_evaluate_sec': 15 * 60,
        'source_sha256': source_shas,
        'reconstruction_status': 'NOT_READY_FOR_ROAD_CLOSURE_INPUT',
        'missing': ['2015 reproduction depth grid with native uncompressed times and georeferencing',
                    'pre-window overflow/inundation initial state',
                    'road/bridge/elevation/class mapping and closure threshold adoption',
                    'forecast generation specification separating timing error from input uncertainty'],
        'no_interpolation_or_dry_state_imputation': True,
    }
    dump('実時間原本時刻・適用性監査.json', output)
    dump('GSI_原本線形状_実時刻.geojson', {'type': 'FeatureCollection', 'features': features})
    dump('BP030_実経過秒_probe.json', {'source_class': 'hypothetical_L2_not_2015_reproduction',
                                       'bp': hydro['bp'], 'series': normalized,
                                       'source_sha256': digest(RAW / 'hydrograph_BP030_probe.json')})
    # Source preservation, unit conversion, and chronology are technical checks, not method adoption.
    assert all(r['elapsed_sec'] == r['elapsed_hours'] * 3600 for r in normalized)
    assert len(features) == sum(r['line_count'] for r in chronology)
    print(json.dumps({k: output[k] for k in ['source_line_features',
          'source_timestamps_within_six_hours_after_reference', 'old_index_timestamp_mismatch_count',
          'api_rising_threshold_intervals', 'reconstruction_status']}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
