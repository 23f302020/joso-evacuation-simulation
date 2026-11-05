"""Audit public USACE results; create research candidates, never runnable closures."""
from pathlib import Path
from datetime import datetime, timedelta, timezone
import csv
import hashlib
import json
import xml.etree.ElementTree as ET
import h5py
import numpy as np
import rasterio
from pyproj import CRS, Transformer
from shapely.geometry import Polygon, LineString, mapping
from shapely.ops import unary_union

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[2]
OUT = BASE / 'derived/usace_candidate_v3'
SOURCE = BASE / 'derived/usace_original/LifeSim_Validation_Joso/Hydraulic_Data'
HDF = SOURCE / 'Calibrated/Calibrated.hdf'
TERRAIN = SOURCE / 'Terrains/Terrain1/Terrain.kinugawa.tif'
NET = ROOT / '04_プログラム/output/sumo/regions/08211/experiments/scenario_c/network/08211_ped.net.xml'
GEOM = 'Geometry/2D Flow Areas/Joso Area/'
SERIES = 'Results/Unsteady/Output/Output Blocks/Base Output/Unsteady Time Series/'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run():
    OUT.mkdir(exist_ok=False)
    with h5py.File(HDF, 'r') as f:
        crs = CRS.from_wkt(f.attrs['Projection'].decode())
        dates = [datetime.strptime(x.decode(), '%d%b%Y %H:%M:%S')
                 for x in f[SERIES + 'Time Date Stamp'][:]]
        sec = np.rint(f[SERIES + 'Time'][:] * 86400).astype(np.int64)
        assert all(dates[i] == dates[0] + timedelta(seconds=int(s)) for i, s in enumerate(sec))
        assert np.all(np.diff(sec) > 0)
        wse = f[SERIES + '2D Flow Areas/Joso Area/Water Surface'][:]
        centers = f[GEOM + 'Cells Center Coordinate'][:]
        vertices = f[GEOM + 'FacePoints Coordinate'][:]
        indexes = f[GEOM + 'Cells FacePoint Indexes'][:]
        min_z = f[GEOM + 'Cells Minimum Elevation'][:]
        areas = f[GEOM + 'Cells Surface Area'][:]
        real_ids = np.where(areas > 0)[0]
        boundary_ids = np.where(areas == 0)[0]
        assert all(np.count_nonzero(indexes[i] >= 0) < 3 for i in boundary_ids)
        polygons = [Polygon(vertices[indexes[i][indexes[i] >= 0]]) for i in real_ids]
        assert wse.shape == (len(sec), len(indexes))
        assert all(p.is_valid and not p.is_empty for p in polygons)
        metadata = {'root_units': f.attrs['Units System'].decode(),
                    'geometry_si_flag': str(f['Geometry'].attrs['SI Units']),
                    'wse_units': f[SERIES + '2D Flow Areas/Joso Area/Water Surface'].attrs['WSEL'].decode(),
                    'file_version': f.attrs['File Version'].decode(),
                    'computation_step': f['Plan Data/Plan Information'].attrs['Computation Time Step'].decode()}
    # Native date strings carry no timezone. JST is an interpretation for event alignment, not an HDF tag.
    np.savez_compressed(OUT / 'native_water_surface.npz', elapsed_seconds=sec, water_surface_m=wse,
                        cell_centers=centers, cell_minimum_elevation_m=min_z,
                        area_cell_ids=real_ids, zero_area_boundary_ids=boundary_ids)
    features = [{'type':'Feature','properties':{'cell_id':int(i)},'geometry':mapping(p)} for i,p in zip(real_ids,polygons)]
    (OUT/'cells_utm54n.geojson').write_text(json.dumps({'type':'FeatureCollection',
        'crs':{'type':'name','properties':{'name':crs.to_string()}},'features':features}),encoding='utf-8')
    with (OUT/'native_times.csv').open('w',encoding='utf-8',newline='') as handle:
        writer=csv.writer(handle);writer.writerow(['index','source_date_no_timezone','elapsed_seconds'])
        writer.writerows((i,d.isoformat(),int(sec[i])) for i,d in enumerate(dates))
    with rasterio.open(TERRAIN) as terrain:
        assert terrain.crs == crs
        terrain_stats={'crs':str(terrain.crs),'resolution_m':terrain.res,'nodata':terrain.nodata}
    domain = unary_union(polygons)
    tree=ET.parse(NET).getroot();location=tree.find('location')
    offset=np.array([float(x) for x in location.attrib['netOffset'].split(',')])
    transform=Transformer.from_crs(CRS.from_user_input(location.attrib['projParameter']),crs,always_xy=True)
    rows=[]
    for edge in tree.findall('edge'):
        if edge.attrib['id'].startswith(':'):continue
        lane=edge.find('lane')
        if lane is None:continue
        xy=np.array([[float(n) for n in p.split(',')[:2]] for p in lane.attrib['shape'].split()])-offset
        xx,yy=transform.transform(xy[:,0],xy[:,1]);line=LineString(zip(xx,yy))
        ratio=line.intersection(domain).length/line.length if line.length else 0
        rows.append({'edge_id':edge.attrib['id'],'domain_coverage_fraction':ratio,
                     'status':'inside_2d' if ratio>1-1e-8 else 'outside_2d' if ratio<1e-8 else 'partial_2d',
                     'road_deck_elevation_status':'unverified','closure_time_sec':''})
    with (OUT/'network_domain_coverage.csv').open('w',encoding='utf-8',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    summary={'created_at_jst':datetime.now(timezone(timedelta(hours=9))).isoformat(),
             'status':'NATIVE_WATER_SURFACE_ACQUIRED_NOT_RUN_READY',
             'source_sha256':{str(p.relative_to(ROOT)):sha(p) for p in [HDF,TERRAIN,NET]},
             'crs':crs.to_string(),'metadata':metadata,'native_count':len(sec),
             'native_interval_sec':np.unique(np.diff(sec)).tolist(),'first':dates[0].isoformat(),
             'last':dates[-1].isoformat(),'timezone_in_source':None,'event_timezone_candidate':'Asia/Tokyo',
             'area_cells':len(polygons),'hdf_cell_columns':len(indexes),
             'zero_area_boundary_columns':len(boundary_ids),
             'nonfinite_wse_count':int(np.count_nonzero(~np.isfinite(wse))),
             'wse_minus_cell_min_range_m':[float(np.nanmin(wse-min_z)),float(np.nanmax(wse-min_z))],
             'terrain':terrain_stats,'road_edges':len(rows),
             'coverage_counts':{s:sum(r['status']==s for r in rows) for s in ['inside_2d','partial_2d','outside_2d']},
             'not_adopted':['evaluation_window','timezone_alignment','road_depth_mapping','outside_domain_policy',
                            'bridge_deck_elevations','closure_thresholds','reopening_policy'],
             'warnings':['Cell minimum depth is not road depth; no road closure was generated.',
                         '300 sec native cadence is not 300 sec accuracy against observations.',
                         'Source geometry SI flag conflicts with root SI label; projected coordinates and terrain agree in meters.',
                         'No source population, life-loss model or evacuation-rate parameters are imported.'],
             'artifact_sha256':{p.name:sha(p) for p in OUT.iterdir() if p.is_file()}}
    (OUT/'audit.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__=='__main__':
    run()
