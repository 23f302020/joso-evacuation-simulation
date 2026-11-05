"""Independent readback directly from the immutable ZIP, not the extractor."""
from pathlib import Path
from datetime import datetime, timezone, timedelta
from io import BytesIO
import csv
import hashlib
import json
import zipfile
import h5py
import numpy as np
from shapely.geometry import shape

BASE=Path(__file__).resolve().parent
ROOT=BASE.parents[2]
CAND=BASE/'derived/usace_candidate_v3'


def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def run():
    checks={}
    zip_path=BASE/'raw/LifeSim_Validation_Joso.zip'
    metadata=json.loads(zip_path.with_suffix('.zip.metadata.json').read_text(encoding='utf-8'))
    checks['zip_sha']=digest(zip_path)==metadata['sha256']
    with zipfile.ZipFile(zip_path) as archive:
        entries=[x for x in archive.infolist() if not x.is_dir()]
        checks['zip_crc']=archive.testzip() is None
        checks['all_extracted_equal_zip']=all((BASE/'derived/usace_original'/x.filename).read_bytes()==archive.read(x) for x in entries)
        name=next(x.filename for x in entries if x.filename.endswith('/Calibrated/Calibrated.hdf'))
        with h5py.File(BytesIO(archive.read(name)),'r') as original:
            prefix='Results/Unsteady/Output/Output Blocks/Base Output/Unsteady Time Series/'
            native=np.load(CAND/'native_water_surface.npz')
            checks['entire_wse_equal_original']=np.array_equal(native['water_surface_m'],original[prefix+'2D Flow Areas/Joso Area/Water Surface'][:])
            dates=[datetime.strptime(x.decode(),'%d%b%Y %H:%M:%S') for x in original[prefix+'Time Date Stamp'][:]]
            seconds=np.array([(d-dates[0]).total_seconds() for d in dates])
            checks['seconds_from_dates_equal_native']=np.array_equal(seconds,native['elapsed_seconds'])
            checks['time_days_agree']=np.allclose(seconds,original[prefix+'Time'][:]*24*60*60,atol=1e-6,rtol=0)
            with (CAND/'native_times.csv').open(encoding='utf-8',newline='') as handle: times=list(csv.DictReader(handle))
            checks['all_csv_times_equal_original']=len(times)==len(dates) and all(datetime.fromisoformat(r['source_date_no_timezone'])==d and int(r['elapsed_seconds'])==s for r,d,s in zip(times,dates,seconds))
            geom=original['Geometry/2D Flow Areas/Joso Area']
            areas=geom['Cells Surface Area'][:]
            checks['boundary_partition']=np.array_equal(np.flatnonzero(areas>0),native['area_cell_ids']) and np.array_equal(np.flatnonzero(areas==0),native['zero_area_boundary_ids'])
            features=json.loads((CAND/'cells_utm54n.geojson').read_text(encoding='utf-8'))['features']
            indexes=geom['Cells FacePoint Indexes'][:];coords=geom['FacePoints Coordinate'][:]
            checks['all_polygon_vertices_equal_original']=len(features)==sum(areas>0) and all(
                np.array_equal(np.asarray(feature['geometry']['coordinates'][0])[:-1],coords[indexes[feature['properties']['cell_id']][indexes[feature['properties']['cell_id']]>=0]]) for feature in features)
            checks['all_polygons_valid']=all(shape(x['geometry']).is_valid for x in features)
            # Window proof only; it does not adopt this evaluation window.
            start=datetime(2015,9,10,12,50);end=start+timedelta(hours=6)
            window=[i for i,d in enumerate(dates) if start<=d<=end]
            checks['proposed_six_hours_native_coverage']=dates[window[0]]==start and dates[window[-1]]==end and all(dates[b]-dates[a]==dates[1]-dates[0] for a,b in zip(window,window[1:]))
            before=native['water_surface_m'][window[0]]-native['cell_minimum_elevation_m']
            initial_wet=int(np.count_nonzero(before[native['area_cell_ids']]>0))
    audit=json.loads((CAND/'audit.json').read_text(encoding='utf-8'))
    checks['candidate_artifact_sha']=all(digest(CAND/name)==sha for name,sha in audit['artifact_sha256'].items())
    with (CAND/'network_domain_coverage.csv').open(encoding='utf-8',newline='') as handle: roads=list(csv.DictReader(handle))
    checks['road_keys_unique_external']=len({r['edge_id'] for r in roads})==len(roads) and all(not r['edge_id'].startswith(':') for r in roads)
    checks['no_invented_closure_or_deck']=all(r['closure_time_sec']=='' and r['road_deck_elevation_status']=='unverified' for r in roads)
    old=json.loads((ROOT/'02_情報調査/交通・地域/jdrt_realistic/仕様調査_保全対象SHA_20261015.json').read_text(encoding='utf-8'))
    checks['old_dependencies_unchanged']=all(digest(ROOT/p)==s for p,s in old['sha256'].items())
    report={'checked_at_jst':datetime.now(timezone(timedelta(hours=9))).isoformat(),
            'technical_result':'PASS' if all(checks.values()) else 'FAIL','checks':checks,
            'zip_files_verified':len(entries),'candidate_wse_shape':list(native['water_surface_m'].shape),
            'proposed_window_native_count':len(window),'initial_cells_wse_above_minimum':initial_wet,
            'initial_wet_role':'cell-minimum diagnostic, not road closure or independent physical truth',
            'simulation_ready':False,'simulation_started':False,
            'source_sha256':metadata['sha256'],'candidate_audit_sha256':digest(CAND/'audit.json')}
    target=BASE/'derived/USACE_独立照合.json'
    target.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))
    if not all(checks.values()):raise SystemExit(1)


if __name__=='__main__':run()
