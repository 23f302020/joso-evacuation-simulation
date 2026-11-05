"""Standalone coverage figure from acquired geometry and existing reference origins."""
from pathlib import Path
import csv
import hashlib
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
from pyproj import Transformer
from shapely.geometry import shape, Point
from shapely.ops import unary_union

BASE=Path(__file__).resolve().parent
ROOT=BASE.parents[2]
CAND=BASE/'derived/usace_candidate_v3'
GEOM=CAND/'cells_utm54n.geojson'
POP=ROOT/'04_プログラム/output/sumo/regions/08211/experiments/scenario_c/inputs/ownership_sensitivity_20260826/non_car_15pct/scenario_c_agent_types.csv'
SHELTER=ROOT/'04_プログラム/output/sumo/regions/08211/derived/shelters_sumo.csv'
OUTPUT=ROOT/'03_研究設計文書/図表・UML/JDRT_実時間版_計算域照合_v1'

def read(path):
    with path.open(encoding='utf-8-sig',newline='') as h:return list(csv.DictReader(h))

def run():
    font=FontProperties(fname='C:/Windows/Fonts/YuGothR.ttc').get_name()
    plt.rcParams.update({'font.family':font,'font.size':12,'svg.fonttype':'none'})
    domain=unary_union([shape(x['geometry']) for x in json.loads(GEOM.read_text())['features']])
    trans=Transformer.from_crs(4326,32654,always_xy=True)
    people=read(POP);facilities=read(SHELTER)
    fig,ax=plt.subplots(figsize=(10,12));fig.set_facecolor('#f6f9f9')
    fig.subplots_adjust(left=.13,right=.98,bottom=.12,top=.89)
    polygons=[domain] if domain.geom_type=='Polygon' else list(domain.geoms)
    for poly in polygons:
        x,y=poly.exterior.xy;ax.fill(x,y,color='#d5ece7',zorder=0);ax.plot(x,y,color='#2e8071',linewidth=1.3)
        for hole in poly.interiors:
            x,y=hole.xy;ax.fill(x,y,color='white')
    for inside,color,label in [(False,'#9aa3ab','計算域外の人口起点'),(True,'#197465','計算域内の人口起点')]:
        rows=[r for r in people if domain.covers(Point(*trans.transform(float(r['lon']),float(r['lat']))))==inside]
        coords=[trans.transform(float(r['lon']),float(r['lat'])) for r in rows]
        ax.scatter([p[0] for p in coords],[p[1] for p in coords],s=[10+int(r['total_pop'])*.2 for r in rows],c=color,alpha=.6,edgecolors='white',linewidths=.4,label=label)
    for r in facilities:
        x,y=trans.transform(float(r['lon']),float(r['lat']));ax.scatter([x],[y],marker='^',s=110,color='#ba643d',edgecolors='white',zorder=4)
        label_offset={'shelter_3':(-55,12),'shelter_4':(10,-16)}.get(r['shelter_id'],(5,5))
        ax.annotate(r['shelter_id'].replace('shelter_','施設'),(x,y),xytext=label_offset,textcoords='offset points',fontsize=11)
    ax.scatter([],[],marker='^',s=110,c='#ba643d',label='既存9施設の位置点')
    ax.set_aspect('equal');ax.set_xlabel('UTM54N 東距 [m]');ax.set_ylabel('UTM54N 北距 [m]')
    ax.ticklabel_format(style='plain',useOffset=False);ax.grid(alpha=.15);ax.legend(loc='upper left',fontsize=11,framealpha=.95)
    ax.set_title('新取得USACE計算域と、既存の人口・避難先\n緑の面は水理計算域。浸水範囲や道路閉鎖ではありません。',fontsize=16,pad=18)
    fig.text(.5,.035,'丸の大きさは元台帳の人口。域内判定は起点の照合です。\n全利用経路や橋梁の安全を保証しません。',ha='center',fontsize=11,color='#5a6570')
    files=[]
    for suffix in ['.svg','.png']:
        path=OUTPUT.with_suffix(suffix)
        fig.savefig(path,dpi=140,bbox_inches='tight');files.append(path)
    plt.close(fig)
    metadata={'role':'coverage verification; not inundation map or simulation result',
              'source_sha256':{p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in [GEOM,POP,SHELTER]},
              'artifact_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in files}}
    OUTPUT.with_suffix('.metadata.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(metadata,ensure_ascii=False))

if __name__=='__main__':run()
