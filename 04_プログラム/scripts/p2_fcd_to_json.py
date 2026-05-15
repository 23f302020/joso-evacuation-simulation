"""Phase 2 可視化: FCD XML → JS変数ファイル + sumo_viz.html 生成。"""

from __future__ import annotations

import argparse
import json
import math
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import pandas as pd

from p2_sumo_env import configure_sumo_environment

configure_sumo_environment(require_tools=True)
import sumolib  # noqa: E402


SCRIPT_DIR = Path(__file__).resolve().parent
PROGRAM_DIR = SCRIPT_DIR.parent

SUMO_DIR = PROGRAM_DIR / "output" / "sumo"
SUMO_DERIVED_DIR = SUMO_DIR / "derived"
SUMO_RESULTS_DIR = SUMO_DIR / "results"
SUMO_VIZ_DIR = SUMO_DIR / "viz"

NET_XML_PATH = SUMO_DIR / "network" / "joso.net.xml"
CLOSURE_TIMELINE_JSON = SUMO_DERIVED_DIR / "closure_timeline_sumo.json"

SIM_DURATION_SEC = 21600
MAP_CENTER = [36.06, 140.00]
MAP_ZOOM = 12

SCENARIO_CFG: dict[str, dict[str, Any]] = {
    "small": {
        "fcd": SUMO_RESULTS_DIR / "scenario_a_small_fcd.xml",
        "vehicle_log": SUMO_RESULTS_DIR / "scenario_a_small_vehicle_log.csv",
        "js_var": "VIZ_VEHICLES_SMALL",
        "js_file": "vehicles_small.js",
        "period_sec": 30,
    },
    "10pct": {
        "fcd": SUMO_RESULTS_DIR / "scenario_a_10pct_fcd.xml",
        "vehicle_log": SUMO_RESULTS_DIR / "scenario_a_10pct_vehicle_log.csv",
        "js_var": "VIZ_VEHICLES_10PCT",
        "js_file": "vehicles_10pct.js",
        "period_sec": 30,
    },
}

HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<title>SUMO避難走行可視化 — 常総市</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script src="vehicles_small.js"></script>
<script src="vehicles_10pct.js"></script>
<script src="closures.js"></script>
<script src="viz_meta.js"></script>
<style>
*{box-sizing:border-box;margin:0;padding:0}
html,body{height:100%}
body{display:flex;flex-direction:column;background:#1a1a2e;color:#e0e0e0;font-family:'Segoe UI',sans-serif}
#legend{padding:8px 16px;background:#16213e;border-bottom:1px solid #0f3460;display:flex;gap:20px;align-items:center;font-size:13px;flex-shrink:0}
.leg{display:flex;align-items:center;gap:6px}
.dot{width:12px;height:12px;border-radius:50%;flex-shrink:0}
.d-run{background:#4fc3f7;border:2px solid #0288d1}
.d-arr{background:#81c784;border:2px solid #388e3c}
.d-blk{background:#ef5350;border:2px solid #c62828}
.road-bar{width:22px;height:4px;background:#ff7043;border-radius:2px;flex-shrink:0}
#map{flex:1;min-height:0}
#controls{padding:10px 16px 12px;background:#0f3460;border-top:1px solid #1a4a8a;flex-shrink:0}
.cr{display:flex;align-items:center;gap:10px;margin-bottom:6px}
.cr:last-child{margin-bottom:0}
#play-btn{background:#e94560;border:none;color:#fff;padding:6px 16px;border-radius:4px;cursor:pointer;font-size:13px;min-width:72px}
#play-btn:hover{background:#c7394f}
#seek{flex:1;accent-color:#e94560;cursor:pointer}
#time-label{font-family:monospace;font-size:14px;min-width:78px;color:#fff}
#stats{font-size:12px;color:#aaa;white-space:nowrap}
.sb{background:#16213e;border:1px solid #4a90d9;color:#4a90d9;padding:3px 10px;border-radius:3px;cursor:pointer;font-size:12px}
.sb.on{background:#4a90d9;color:#000;font-weight:bold}
.sb:hover:not(.on){background:#1e2f50}
.scenario-select{background:#16213e;border:1px solid #4a90d9;color:#e0e0e0;padding:3px 8px;border-radius:3px;font-size:12px}
.scenario-select:disabled{opacity:.6}
#info{font-size:12px;color:#888;margin-left:auto}
</style>
</head>
<body>
<div id="legend">
  <strong style="color:#aaa">凡例：</strong>
  <div class="leg"><div class="dot d-run"></div>走行中</div>
  <div class="leg"><div class="dot d-arr"></div>到着</div>
  <div class="leg"><div class="dot d-blk"></div>逃げ遅れ・出発不可</div>
  <div class="leg"><div class="road-bar"></div>閉鎖道路</div>
</div>
<div id="map"></div>
<div id="controls">
  <div class="cr">
    <button id="play-btn">▶ 再生</button>
    <input type="range" id="seek" min="0" max="21600" value="0" step="30">
    <span id="time-label">00:00:00</span>
    <span id="stats">走行中 0 / 到着 0 / 逃げ遅れ 0</span>
  </div>
  <div class="cr">
    <span style="font-size:12px;color:#aaa">シナリオ：</span>
    <select id="scenario-select" class="scenario-select"></select>
    <span style="font-size:12px;color:#aaa">速度倍率：</span>
    <button class="sb" data-s="1">×1</button>
    <button class="sb" data-s="5">×5</button>
    <button class="sb on" data-s="10">×10</button>
    <button class="sb" data-s="60">×60</button>
    <span id="info"></span>
  </div>
</div>
<script>
(function(){
  var meta=window.VIZ_META||{map_center:[36.06,140.00],map_zoom:12,sim_duration_sec:21600};
  var cl=window.VIZ_CLOSURES||{edge_coords:{},events:[]};
  var datasets=[
    {name:'small',label:'small',data:window.VIZ_VEHICLES_SMALL||null},
    {name:'10pct',label:'10pct',data:window.VIZ_VEHICLES_10PCT||null}
  ].filter(function(d){return!!d.data;});
  var vd=datasets.length?datasets[0].data:null;
  var SIM_MAX=meta.sim_duration_sec||21600;
  var scenarioSelect=document.getElementById('scenario-select');
  document.getElementById('seek').max=SIM_MAX;
  if(scenarioSelect){
    datasets.forEach(function(d){
      var opt=document.createElement('option');
      opt.value=d.name;
      opt.textContent=d.label+' ('+d.data.vehicle_count+'台)';
      scenarioSelect.appendChild(opt);
    });
    scenarioSelect.disabled=datasets.length<=1;
  }
  if(vd)document.getElementById('info').textContent='シナリオ: '+vd.scenario+'  車両数: '+vd.vehicle_count;
  else document.getElementById('info').textContent='車両データなし';

  var map=L.map('map').setView(meta.map_center,meta.map_zoom);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{
    attribution:'&copy; OpenStreetMap contributors',maxZoom:19
  }).addTo(map);

  var ec=cl.edge_coords||{};
  var cg=(cl.events||[]).map(function(ev){
    var g=L.layerGroup();
    (ev.new_edge_ids||[]).forEach(function(eid){
      var pts=ec[eid];
      if(pts&&pts.length>=2)L.polyline(pts.map(function(p){return[p[1],p[0]];}),
        {color:'#ff7043',weight:3,opacity:0.85}).addTo(g);
    });
    return{t:ev.sim_time_sec,g:g};
  });

  var mm={};
  var SR={color:'#0288d1',fillColor:'#4fc3f7',fillOpacity:0.9,radius:5,weight:1};
  var SA={color:'#388e3c',fillColor:'#81c784',fillOpacity:0.7,radius:4,weight:1};
  var SB={color:'#c62828',fillColor:'#ef5350',fillOpacity:0.8,radius:5,weight:1};

  function clearVehicles(){
    Object.keys(mm).forEach(function(vid){map.removeLayer(mm[vid]);});
    mm={};
  }

  function initVehicles(){
    clearVehicles();
    if(!vd){
      document.getElementById('info').textContent='車両データなし';
      return;
    }
    Object.keys(vd.vehicles).forEach(function(vid){
      var m=L.circleMarker(meta.map_center,SR);
      m.setStyle({opacity:0,fillOpacity:0});
      m.addTo(map);
      mm[vid]=m;
    });
    document.getElementById('info').textContent='シナリオ: '+vd.scenario+'  車両数: '+vd.vehicle_count;
  }

  function selectDataset(name){
    var found=datasets.filter(function(d){return d.name===name;})[0];
    if(!found)return;
    vd=found.data;
    curT=0;
    lastTs=null;
    initVehicles();
    render(0);
  }

  function lerp(fr,t){
    if(!fr||fr.length===0)return null;
    if(t<fr[0][0])return null;
    var lo=0,hi=fr.length-1;
    while(lo<hi){var mid=(lo+hi+1)>>1;if(fr[mid][0]<=t)lo=mid;else hi=mid-1;}
    var f0=fr[lo];
    if(lo+1>=fr.length)return[f0[2],f0[1]];
    var f1=fr[lo+1],a=(t-f0[0])/(f1[0]-f0[0]);
    return[f0[2]+a*(f1[2]-f0[2]),f0[1]+a*(f1[1]-f0[1])];
  }

  function fmt(s){
    var h=Math.floor(s/3600),m=Math.floor((s%3600)/60),ss=s%60;
    return(h<10?'0':'')+h+':'+(m<10?'0':'')+m+':'+(ss<10?'0':'')+ss;
  }

  var ac=0;
  function render(t){
    var ti=Math.round(t),nr=0,na=0,nb=0;
    if(vd){
      var vs=vd.vehicles;
      for(var vid in vs){
        var m=mm[vid];if(!m)continue;
        var v=vs[vid];
        var pos=lerp(v.frames,ti);
        if(pos===null){m.setStyle({opacity:0,fillOpacity:0});continue;}
        m.setLatLng(pos);
        if(v.status==='blocked'||v.status==='stranded'){m.setStyle(SB);nb++;continue;}
        var lt=v.frames[v.frames.length-1][0];
        if(ti>=lt){m.setStyle(SA);na++;}else{m.setStyle(SR);nr++;}
      }
    }
    while(ac<cg.length&&cg[ac].t<=ti)cg[ac++].g.addTo(map);
    while(ac>0&&cg[ac-1].t>ti)cg[--ac].g.remove();
    document.getElementById('time-label').textContent=fmt(ti);
    document.getElementById('seek').value=ti;
    document.getElementById('stats').textContent='走行中 '+nr+' / 到着 '+na+' / 逃げ遅れ '+nb;
  }

  var curT=0,playing=false,spd=10,lastTs=null;
  function tick(ts){
    if(!playing)return;
    if(lastTs!==null)curT=Math.min(curT+(ts-lastTs)/1000*spd,SIM_MAX);
    lastTs=ts;render(curT);
    if(curT<SIM_MAX)requestAnimationFrame(tick);
    else{playing=false;lastTs=null;document.getElementById('play-btn').textContent='▶ 再生';}
  }

  document.getElementById('play-btn').addEventListener('click',function(){
    if(playing){playing=false;lastTs=null;document.getElementById('play-btn').textContent='▶ 再生';}
    else{if(curT>=SIM_MAX)curT=0;playing=true;
      document.getElementById('play-btn').textContent='⏸ 停止';requestAnimationFrame(tick);}
  });
  document.getElementById('seek').addEventListener('input',function(e){
    curT=+e.target.value;lastTs=null;render(curT);
  });
  document.querySelectorAll('.sb').forEach(function(b){
    b.addEventListener('click',function(){
      spd=+b.dataset.s;
      document.querySelectorAll('.sb').forEach(function(x){x.classList.remove('on');});
      b.classList.add('on');
    });
  });
  if(scenarioSelect){
    scenarioSelect.addEventListener('change',function(e){selectDataset(e.target.value);});
  }
  initVehicles();
  render(0);
})();
</script>
</body>
</html>
"""


def ensure_dirs() -> None:
    SUMO_VIZ_DIR.mkdir(parents=True, exist_ok=True)


def parse_fcd_xml(fcd_path: Path) -> dict[str, list[list]]:
    vehicles: dict[str, list[list]] = {}
    current_time = 0.0
    for _, elem in ET.iterparse(str(fcd_path), events=("start",)):
        if elem.tag == "timestep":
            current_time = float(elem.get("time", 0))
        elif elem.tag == "vehicle":
            vid = elem.get("id", "")
            lon = round(float(elem.get("x", 0)), 6)
            lat = round(float(elem.get("y", 0)), 6)
            speed = round(float(elem.get("speed", 0)), 2)
            if vid not in vehicles:
                vehicles[vid] = []
            vehicles[vid].append([int(current_time), lon, lat, speed])
    return vehicles


def load_vehicle_status(log_path: Path) -> dict[str, str]:
    df = pd.read_csv(log_path, dtype=str)
    result: dict[str, str] = {}
    for _, row in df.iterrows():
        vid = str(row["vehicle_id"])
        if row.get("departure_blocked_by_closure", "False") == "True":
            result[vid] = "blocked"
        elif row.get("stranded_main", "False") == "True":
            result[vid] = "stranded"
        elif row.get("arrived", "False") == "True":
            result[vid] = "arrived"
        else:
            result[vid] = "unknown"
    return result


def load_all_edge_coords(net: Any) -> dict[str, list[list[float]]]:
    with open(CLOSURE_TIMELINE_JSON, encoding="utf-8") as f:
        timeline = json.load(f)

    edge_ids: set[str] = set()
    for event in timeline["closures"]:
        edge_ids.update(event["closed_sumo_edge_ids"])

    coords: dict[str, list[list[float]]] = {}
    failed = 0
    for eid in edge_ids:
        try:
            edge = net.getEdge(eid)
            pts: list[list[float]] = []
            for x, y in edge.getShape():
                lon, lat = net.convertXY2LonLat(x, y)
                pts.append([round(lon, 6), round(lat, 6)])
            if len(pts) >= 2:
                coords[eid] = pts
        except Exception:
            failed += 1
    if failed:
        print(f"[WARN] {failed} edges could not be resolved from net.xml")
    return coords


def build_incremental_events(edge_coords: dict[str, list[list[float]]]) -> list[dict]:
    with open(CLOSURE_TIMELINE_JSON, encoding="utf-8") as f:
        timeline = json.load(f)

    events: list[dict] = []
    prev_ids: set[str] = set()
    for event in timeline["closures"]:
        current_ids = set(event["closed_sumo_edge_ids"])
        new_ids = sorted(current_ids - prev_ids)
        events.append(
            {
                "sim_time_sec": event["sim_time_sec"],
                "time_id": event["time_id"],
                "new_edge_ids": new_ids,
            }
        )
        prev_ids = current_ids
    return events


def write_js(path: Path, var_name: str, data: Any) -> None:
    path.write_text(
        f"window.{var_name} = {json.dumps(data, ensure_ascii=False, separators=(',', ':'))};\n",
        encoding="utf-8",
    )
    size_kb = path.stat().st_size // 1024
    print(f"[INFO] saved: {path} ({size_kb} KB)")


def cmd_vehicles(scenario_name: str) -> None:
    ensure_dirs()
    cfg = SCENARIO_CFG[scenario_name]
    fcd_path: Path = cfg["fcd"]
    log_path: Path = cfg["vehicle_log"]

    if not fcd_path.exists():
        raise FileNotFoundError(
            f"FCD file not found: {fcd_path}\n"
            "  → p2_sumo_scenario.py で再生成し、TraCI シナリオを再実行してください。"
        )

    print(f"[INFO] parsing FCD: {fcd_path.name}")
    fcd_vehicles = parse_fcd_xml(fcd_path)
    status_map = load_vehicle_status(log_path) if log_path.exists() else {}

    vehicles_obj: dict[str, Any] = {
        vid: {"frames": frames, "status": status_map.get(vid, "unknown")}
        for vid, frames in fcd_vehicles.items()
    }
    data: dict[str, Any] = {
        "scenario": scenario_name,
        "period_sec": cfg["period_sec"],
        "sim_duration_sec": SIM_DURATION_SEC,
        "vehicle_count": len(vehicles_obj),
        "vehicles": vehicles_obj,
    }
    write_js(SUMO_VIZ_DIR / cfg["js_file"], cfg["js_var"], data)
    print(f"[INFO] {len(vehicles_obj)} vehicles")


def cmd_closures() -> None:
    ensure_dirs()
    print("[INFO] loading net.xml ...")
    net = sumolib.net.readNet(str(NET_XML_PATH))
    edge_coords = load_all_edge_coords(net)
    events = build_incremental_events(edge_coords)

    referenced: set[str] = set()
    for ev in events:
        referenced.update(ev["new_edge_ids"])
    coords_filtered = {k: v for k, v in edge_coords.items() if k in referenced}

    data: dict[str, Any] = {"edge_coords": coords_filtered, "events": events}
    write_js(SUMO_VIZ_DIR / "closures.js", "VIZ_CLOSURES", data)
    total = sum(len(ev["new_edge_ids"]) for ev in events)
    print(f"[INFO] {len(events)} events, {total} new-edge entries")


def cmd_meta() -> None:
    ensure_dirs()
    scenarios = [
        s for s in ["small", "10pct"] if (SUMO_VIZ_DIR / SCENARIO_CFG[s]["js_file"]).exists()
    ]
    data: dict[str, Any] = {
        "scenarios": scenarios,
        "sim_duration_sec": SIM_DURATION_SEC,
        "map_center": MAP_CENTER,
        "map_zoom": MAP_ZOOM,
    }
    write_js(SUMO_VIZ_DIR / "viz_meta.js", "VIZ_META", data)


def cmd_html() -> None:
    ensure_dirs()
    out_path = SUMO_VIZ_DIR / "sumo_viz.html"
    out_path.write_text(HTML_TEMPLATE, encoding="utf-8")
    print(f"[INFO] saved: {out_path}")


def cmd_sample() -> None:
    """サンプルデータ（SUMO不要）で可視化を確認する。"""
    ensure_dirs()

    origins = [
        (139.970, 36.025), (139.980, 36.035), (139.990, 36.020),
        (139.960, 36.045), (139.975, 36.055), (140.005, 36.040),
        (140.015, 36.030), (139.955, 36.060), (139.985, 36.065),
        (140.010, 36.050),
    ]
    shelter = (139.998, 36.073)
    period = 30
    vehicles: dict[str, Any] = {}
    for i, (olon, olat) in enumerate(origins):
        vid = f"veh_small_origin_{i + 1:04d}_0001"
        duration = 900 + i * 300
        dlon = shelter[0] - olon
        dlat = shelter[1] - olat
        dist_m = math.hypot(
            dlon * 111320 * math.cos(math.radians(olat)),
            dlat * 110540,
        )
        speed = round(dist_m / duration, 2)
        frames: list[list] = []
        t = 0
        while t <= duration:
            alpha = t / duration
            frames.append([t, round(olon + alpha * dlon, 6), round(olat + alpha * dlat, 6), speed])
            t += period
        vehicles[vid] = {"frames": frames, "status": "arrived" if i < 8 else "blocked"}

    write_js(
        SUMO_VIZ_DIR / "vehicles_small.js",
        "VIZ_VEHICLES_SMALL",
        {
            "scenario": "small",
            "period_sec": period,
            "sim_duration_sec": SIM_DURATION_SEC,
            "vehicle_count": len(vehicles),
            "vehicles": vehicles,
        },
    )

    write_js(
        SUMO_VIZ_DIR / "closures.js",
        "VIZ_CLOSURES",
        {
            "edge_coords": {
                "sample_edge_0": [[139.975, 36.030], [139.980, 36.035], [139.985, 36.038]],
                "sample_edge_1": [[139.990, 36.025], [139.995, 36.028], [140.000, 36.032]],
                "sample_edge_2": [[140.000, 36.045], [140.005, 36.048], [140.008, 36.052]],
            },
            "events": [
                {
                    "sim_time_sec": 789,
                    "time_id": "t0",
                    "new_edge_ids": ["sample_edge_0", "sample_edge_1"],
                },
                {
                    "sim_time_sec": 1800,
                    "time_id": "t1",
                    "new_edge_ids": ["sample_edge_2"],
                },
            ],
        },
    )

    write_js(
        SUMO_VIZ_DIR / "viz_meta.js",
        "VIZ_META",
        {
            "scenarios": ["small"],
            "sim_duration_sec": SIM_DURATION_SEC,
            "map_center": MAP_CENTER,
            "map_zoom": MAP_ZOOM,
        },
    )

    cmd_html()
    print(f"[INFO] sample 完了 → {SUMO_VIZ_DIR / 'sumo_viz.html'}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=["vehicles-small", "vehicles-10pct", "closures", "meta", "html", "sample", "all"],
        help="実行する処理",
    )
    args = parser.parse_args()

    if args.command == "vehicles-small":
        cmd_vehicles("small")
    elif args.command == "vehicles-10pct":
        cmd_vehicles("10pct")
    elif args.command == "closures":
        cmd_closures()
    elif args.command == "meta":
        cmd_meta()
    elif args.command == "html":
        cmd_html()
    elif args.command == "sample":
        cmd_sample()
    elif args.command == "all":
        for scenario_name in ["small", "10pct"]:
            if SCENARIO_CFG[scenario_name]["fcd"].exists():
                cmd_vehicles(scenario_name)
            else:
                print(f"[WARN] skip vehicles-{scenario_name}: FCD file not found")
        cmd_closures()
        cmd_meta()
        cmd_html()


if __name__ == "__main__":
    main()
