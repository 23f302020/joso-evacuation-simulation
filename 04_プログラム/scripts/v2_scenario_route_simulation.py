"""Phase 1 v2: シナリオ型浸水拡大・任意地点ルート検索HTMLを生成する。"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import geopandas as gpd
import osmnx as ox
import pandas as pd
from shapely import wkt
from shapely.geometry import Point, mapping

import config
from i1_spatial_join import build_closure_dict, build_closure_diagnostics, load_edges
from i3_route_search import find_nearest_node, load_shelters

SCENARIO_VERSION = "scenario_v2"
SCENARIO_TITLE = "Phase 1 v2 シミュレーション版"

SCRIPT_DIR = Path(__file__).resolve().parent
OUTPUT_ROOT = (SCRIPT_DIR / config.OUTPUT_DIR).resolve()
SCENARIO_DIR = OUTPUT_ROOT / SCENARIO_VERSION
SCENARIO_ASSETS_DIR = SCENARIO_DIR / "assets"

SCENARIO_HTML_PATH = SCENARIO_DIR / "scenario_route_simulation.html"
SCENARIO_DATA_JS_PATH = SCENARIO_ASSETS_DIR / "scenario_v2_data.js"
SCENARIO_APP_JS_PATH = SCENARIO_ASSETS_DIR / "scenario_v2_app.js"
SCENARIO_CSS_PATH = SCENARIO_ASSETS_DIR / "scenario_v2.css"
SCENARIO_SUMMARY_CSV_PATH = SCENARIO_DIR / "scenario_v2_summary.csv"

# 浸水ナビ調査で2015年実破堤点に最も近いと整理済みの BP030。
BREACH_POINT = {
    "name": "BP030 近傍破堤点",
    "lat": 36.0885,
    "lon": 139.9633,
    "note": "左岸19.5km。2015年実破堤点（左岸21k）に最も近い浸水ナビ破堤点候補。",
}

# 破堤（12:50）から各 KML タイムスタンプまでの経過時間（h）。
# これを総経過時間（141.5h）で割った比率を距離分位点として使用する（P1-S2 確定案）。
_ELAPSED_H = [5.2, 17.2, 29.2, 41.2, 53.2, 65.2, 77.2, 141.5]
_TOTAL_H = 141.5
SCENARIO_PROGRESS = [h / _TOTAL_H for h in _ELAPSED_H]

CRS_METRIC = "EPSG:6690"


def _resolve(path: str) -> Path:
    return (SCRIPT_DIR / path).resolve()


def ensure_output_dirs() -> None:
    SCENARIO_ASSETS_DIR.mkdir(parents=True, exist_ok=True)


def _load_joso_boundary() -> gpd.GeoDataFrame:
    """N03 Shapefile から常総市の行政区域ポリゴンを返す（EPSG:6668）。"""
    n03 = gpd.read_file(str(_resolve(config.N03_SHP_PATH)), engine="pyogrio")
    joso = n03[n03["N03_007"] == config.JOSO_CODE].copy()
    if joso.empty:
        raise ValueError(f"N03 から常総市 ({config.JOSO_CODE}) を取得できませんでした")
    return joso.to_crs(config.CRS_JGD2011)


def load_final_flood_area() -> gpd.GeoDataFrame:
    """A31a waterDepth≥2 を N03 常総市境界でクリップして最終浸水範囲を返す（P1-S1 確定案）。

    flood_polygons.pkl は一部時点がフォールバック（茨城県全域 8792件）を含むため、
    A31a GML を直接ロードして常総市範囲に限定する。
    """
    from e1_load_flood_data import load_a31a_gml

    a31a = load_a31a_gml(str(_resolve(config.GML_DIR)))
    joso_boundary = _load_joso_boundary()
    joso_union = gpd.GeoDataFrame(
        geometry=[joso_boundary.geometry.union_all()], crs=config.CRS_JGD2011
    )
    joined = gpd.sjoin(a31a, joso_union, how="inner", predicate="intersects")
    final_gdf = a31a.loc[joined.index.unique()].copy()
    if final_gdf.empty:
        raise ValueError("常総市内に A31a waterDepth≥2 ポリゴンが見つかりません")
    print(f"[v2] final flood area: {len(final_gdf)} polygons (A31a waterDepth>=2, Joso)")
    return final_gdf


def build_scenario_flood_dict(
    final_gdf: gpd.GeoDataFrame,
) -> tuple[dict[str, gpd.GeoDataFrame], list[dict[str, Any]]]:
    """破堤点からの距離順で最終浸水範囲をt0〜t7へ累積分割する。"""
    metric = final_gdf.to_crs(CRS_METRIC).copy()
    breach_metric = (
        gpd.GeoSeries(
            [Point(BREACH_POINT["lon"], BREACH_POINT["lat"])],
            crs=config.CRS_WGS84,
        )
        .to_crs(CRS_METRIC)
        .iloc[0]
    )
    distances = metric.geometry.centroid.distance(breach_metric)
    metric["_distance_m"] = distances
    scenario: dict[str, gpd.GeoDataFrame] = {}
    summary: list[dict[str, Any]] = []

    for idx, (timestamp, progress) in enumerate(zip(config.KML_TIMESTAMPS, SCENARIO_PROGRESS)):
        threshold = distances.quantile(progress)
        selected = metric[distances <= threshold].copy()
        if selected.empty:
            selected = metric.nsmallest(1, "_distance_m").copy()
        selected = selected.drop(columns=["_distance_m"], errors="ignore")
        selected = selected.to_crs(config.CRS_JGD2011)
        scenario[timestamp] = selected
        summary.append(
            {
                "id": f"t{idx}",
                "timestamp": timestamp,
                "progress_ratio": progress,
                "flood_polygon_count": len(selected),
            }
        )
    return scenario, summary


def _thin_coords(coords: list[tuple[float, float]], max_points: int = 10) -> list[tuple[float, float]]:
    if len(coords) <= max_points:
        return coords
    step = max(1, math.ceil(len(coords) / (max_points - 1)))
    thinned = coords[::step]
    if thinned[-1] != coords[-1]:
        thinned.append(coords[-1])
    return thinned


def _edge_coords(data: dict[str, Any], u_data: dict[str, Any], v_data: dict[str, Any]) -> list[list[float]]:
    geom = data.get("geometry")
    if isinstance(geom, str):
        try:
            geom = wkt.loads(geom)
        except Exception:
            geom = None
    if geom is not None and hasattr(geom, "coords"):
        coords = [(float(lat), float(lon)) for lon, lat in geom.coords]
        coords = _thin_coords(coords)
    else:
        coords = [
            (float(u_data["y"]), float(u_data["x"])),
            (float(v_data["y"]), float(v_data["x"])),
        ]
    return [[round(lat, 6), round(lon, 6)] for lat, lon in coords]


def build_graph_payload(G) -> dict[str, Any]:
    nodes = {
        str(node_id): [round(float(data["y"]), 6), round(float(data["x"]), 6)]
        for node_id, data in G.nodes(data=True)
    }
    edges: list[dict[str, Any]] = []
    for u, v, key, data in G.edges(keys=True, data=True):
        edge_id = f"{u}_{v}_{key}"
        length = float(data.get("length") or 1.0)
        edges.append(
            {
                "id": edge_id,
                "u": str(u),
                "v": str(v),
                "length": round(length, 2),
                "coords": _edge_coords(data, G.nodes[u], G.nodes[v]),
            }
        )
    return {"nodes": nodes, "edges": edges}


def build_shelter_payload(G) -> list[dict[str, Any]]:
    shelters = load_shelters(str(_resolve(config.SHELTER_SHP_PATH)))
    rows: list[dict[str, Any]] = []
    for idx, row in enumerate(shelters.itertuples(index=False)):
        node = find_nearest_node(G, float(row.lon), float(row.lat))
        rows.append(
            {
                "id": f"shelter_{idx}",
                "name": str(row.name),
                "capacity": int(row.capacity),
                "lat": round(float(row.lat), 6),
                "lon": round(float(row.lon), 6),
                "node": str(node),
            }
        )
    return rows


def _compact_flood_geojson(gdf: gpd.GeoDataFrame) -> dict[str, Any]:
    flood_wgs = gdf.to_crs(config.CRS_WGS84)
    union = flood_wgs.geometry.union_all().simplify(0.00004, preserve_topology=True)
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {},
                "geometry": mapping(union),
            }
        ],
    }


def build_flood_payload(scenario_flood: dict[str, gpd.GeoDataFrame]) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for idx, timestamp in enumerate(config.KML_TIMESTAMPS):
        payload[f"t{idx}"] = _compact_flood_geojson(scenario_flood[timestamp])
    return payload


def build_time_payload(summary_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    payload: list[dict[str, Any]] = []
    for idx, (timestamp, row) in enumerate(zip(config.KML_TIMESTAMPS, summary_rows)):
        payload.append(
            {
                "id": f"t{idx}",
                "label": f"t{idx}",
                "timestamp": timestamp,
                "progressPercent": round(float(row["progress_ratio"]) * 100),
            }
        )
    return payload


def build_support_area_payload(_G) -> dict[str, Any]:
    """シミュレーション対応地域として config.JOSO_BBOX の範囲を返す。"""
    south = config.BBOX_SOUTH
    north = config.BBOX_NORTH
    west  = config.BBOX_WEST
    east  = config.BBOX_EAST
    lat_pad = max((north - south) * 0.2, 0.01)
    lon_pad = max((east - west) * 0.2, 0.01)
    return {
        "label": "常総市道路ネットワーク範囲",
        "bounds": [
            [round(south, 6), round(west, 6)],
            [round(north, 6), round(east, 6)],
        ],
        "maxBounds": [
            [round(south - lat_pad, 6), round(west - lon_pad, 6)],
            [round(north + lat_pad, 6), round(east + lon_pad, 6)],
        ],
    }


def build_data_payload(
    G,
    scenario_flood: dict[str, gpd.GeoDataFrame],
    closure_dict: dict[str, list[str]],
    summary_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    closures: dict[str, list[str]] = {}
    for idx, timestamp in enumerate(config.KML_TIMESTAMPS):
        closures[f"t{idx}"] = closure_dict.get(timestamp, [])

    support_area = build_support_area_payload(G)
    south_west, north_east = support_area["bounds"]
    map_center = [
        round((south_west[0] + north_east[0]) / 2, 6),
        round((south_west[1] + north_east[1]) / 2, 6),
    ]
    return {
        "version": SCENARIO_VERSION,
        "title": SCENARIO_TITLE,
        "map": {"center": map_center, "zoom": 12},
        "supportArea": support_area,
        "breachPoint": BREACH_POINT,
        "times": build_time_payload(summary_rows),
        "floods": build_flood_payload(scenario_flood),
        "closures": closures,
        "graph": build_graph_payload(G),
        "shelters": build_shelter_payload(G),
    }


def save_data_js(payload: dict[str, Any]) -> None:
    text = "window.SCENARIO_V2_DATA = "
    text += json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    text += ";\n"
    SCENARIO_DATA_JS_PATH.write_text(text, encoding="utf-8")


def save_summary_csv(
    summary_rows: list[dict[str, Any]],
    closure_dict: dict[str, list[str]],
) -> None:
    rows = []
    for idx, (timestamp, row) in enumerate(zip(config.KML_TIMESTAMPS, summary_rows)):
        rows.append(
            {
                **row,
                "closed_edge_count": len(closure_dict.get(timestamp, [])),
                "flood_source": "A31a_08_10_waterDepth_ge2_Joso",
                "breach_point": BREACH_POINT["name"],
                "breach_lat": BREACH_POINT["lat"],
                "breach_lon": BREACH_POINT["lon"],
            }
        )
    pd.DataFrame(rows).to_csv(SCENARIO_SUMMARY_CSV_PATH, index=False)


def save_html() -> None:
    html = """<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Phase 1 v2 シミュレーション版</title>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
  <link rel="stylesheet" href="assets/scenario_v2.css">
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js" defer></script>
  <script src="assets/scenario_v2_data.js" defer></script>
  <script src="assets/scenario_v2_app.js" defer></script>
</head>
<body>
  <main class="app-shell">
    <aside class="panel" aria-label="シミュレーション操作">
      <p class="eyebrow">Phase 1 v2</p>
      <h1>シミュレーション版</h1>
      <p class="lead">時刻を選び、地図上の任意地点をクリックすると、浸水道路を避けて到達可能な最寄り避難所までのルートを検索します。</p>

      <section class="control-group">
        <h2>時刻</h2>
        <div id="time-buttons" class="time-grid"></div>
      </section>

      <section class="control-group">
        <h2>状態</h2>
        <dl class="status-list">
          <div>
            <dt>浸水進行</dt>
            <dd id="status-progress">-</dd>
          </div>
          <div>
            <dt>閉鎖道路</dt>
            <dd id="status-closures">-</dd>
          </div>
          <div>
            <dt>避難所</dt>
            <dd id="status-shelters">-</dd>
          </div>
          <div>
            <dt>対象地域</dt>
            <dd id="status-area">-</dd>
          </div>
        </dl>
      </section>

      <section class="control-group">
        <h2>検索結果</h2>
        <div id="route-result" class="result-box">地図上の地点をクリックしてください。</div>
      </section>

      <a class="back-link" href="../index.html">トップページへ戻る</a>
    </aside>
    <section class="map-wrap" aria-label="シミュレーション地図">
      <div id="map"></div>
    </section>
  </main>
</body>
</html>
"""
    SCENARIO_HTML_PATH.write_text(html, encoding="utf-8")


def save_css() -> None:
    css = """:root {
  color-scheme: light;
  --bg: #ffffff;
  --text: #1f2933;
  --muted: #6b7280;
  --line: #d9dee5;
  --surface: #f8fafc;
  --surface-hover: #eef2f7;
  --accent: #2563eb;
  --danger: #dc2626;
}

* {
  box-sizing: border-box;
}

body {
  margin: 0;
  min-height: 100vh;
  background: var(--bg);
  color: var(--text);
  font-family: "Yu Gothic", "Meiryo", system-ui, sans-serif;
}

.app-shell {
  display: grid;
  grid-template-columns: 340px minmax(0, 1fr);
  min-height: 100vh;
}

.panel {
  border-right: 1px solid var(--line);
  padding: 28px 24px;
  background: var(--bg);
  overflow-y: auto;
}

.eyebrow {
  margin: 0;
  color: var(--muted);
  font-size: 13px;
}

h1 {
  margin: 4px 0 8px;
  font-size: 26px;
  line-height: 1.25;
  letter-spacing: 0;
}

.lead {
  margin: 0 0 24px;
  color: var(--muted);
  font-size: 14px;
  line-height: 1.7;
}

.control-group {
  margin-top: 24px;
}

h2 {
  margin: 0 0 10px;
  font-size: 15px;
  letter-spacing: 0;
}

.time-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
}

.time-button {
  min-height: 42px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--bg);
  color: var(--text);
  font: inherit;
  cursor: pointer;
}

.time-button:hover,
.time-button:focus-visible {
  border-color: var(--accent);
  background: var(--surface-hover);
  outline: none;
}

.time-button[aria-pressed="true"] {
  border-color: var(--accent);
  background: #eff6ff;
  color: #1d4ed8;
  font-weight: 700;
}

.status-list {
  margin: 0;
}

.status-list div {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  padding: 8px 0;
  border-bottom: 1px solid var(--line);
}

dt {
  color: var(--muted);
  font-size: 13px;
}

dd {
  margin: 0;
  font-weight: 700;
}

.result-box {
  min-height: 112px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--surface);
  padding: 12px;
  font-size: 14px;
  line-height: 1.6;
}

.result-box strong {
  display: block;
  margin-bottom: 4px;
}

.back-link {
  display: inline-flex;
  margin-top: 24px;
  color: var(--accent);
  font-size: 14px;
  text-decoration: none;
}

.map-wrap,
#map {
  min-height: 100vh;
}

.legend {
  border: 1px solid var(--line);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.95);
  padding: 10px 12px;
  line-height: 1.7;
  font-size: 13px;
}

.legend-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.swatch {
  width: 18px;
  height: 4px;
  border-radius: 99px;
  display: inline-block;
}

.swatch-flood {
  height: 12px;
  background: rgba(37, 99, 235, 0.3);
  border: 1px solid #1d4ed8;
}

.swatch-closed {
  background: var(--danger);
}

.swatch-route {
  background: #111827;
}

.swatch-area {
  height: 12px;
  border: 2px solid #047857;
  background: transparent;
}

.swatch-outside {
  height: 12px;
  background: rgba(31, 41, 55, 0.18);
  border: 1px solid rgba(31, 41, 55, 0.4);
}

@media (max-width: 860px) {
  .app-shell {
    grid-template-columns: 1fr;
  }

  .panel {
    border-right: 0;
    border-bottom: 1px solid var(--line);
  }

  .map-wrap,
  #map {
    min-height: 66vh;
  }
}
"""
    SCENARIO_CSS_PATH.write_text(css, encoding="utf-8")


def save_app_js() -> None:
    js = r"""(function () {
  const data = window.SCENARIO_V2_DATA;
  if (!data) return;

  const supportBounds = L.latLngBounds(data.supportArea.bounds);
  const map = L.map("map", {
    maxBounds: data.supportArea.maxBounds,
    maxBoundsViscosity: 0.85
  }).setView(data.map.center, data.map.zoom);
  L.tileLayer("https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png", {
    maxZoom: 19,
    attribution: "&copy; OpenStreetMap contributors &copy; CARTO"
  }).addTo(map);

  const outsideLayer = L.layerGroup().addTo(map);
  const floodLayer = L.geoJSON(null, {
    style: {
      color: "#1d4ed8",
      weight: 1,
      fillColor: "#2563eb",
      fillOpacity: 0.28
    }
  }).addTo(map);
  const closedLayer = L.layerGroup().addTo(map);
  const routeLayer = L.layerGroup().addTo(map);
  const markerLayer = L.layerGroup().addTo(map);
  const shelterLayer = L.layerGroup().addTo(map);

  const nodes = data.graph.nodes;
  const edgesById = new Map();
  const adjacency = new Map();

  function addOutsideMask() {
    const south = supportBounds.getSouth();
    const north = supportBounds.getNorth();
    const west = supportBounds.getWest();
    const east = supportBounds.getEast();
    const style = {
      color: "#1f2937",
      weight: 0,
      fillColor: "#1f2937",
      fillOpacity: 0.18,
      interactive: false
    };
    [
      [[-90, -180], [south, 180]],
      [[north, -180], [90, 180]],
      [[south, -180], [north, west]],
      [[south, east], [north, 180]]
    ].forEach((bounds) => L.rectangle(bounds, style).addTo(outsideLayer));
  }

  addOutsideMask();
  map.fitBounds(supportBounds);

  for (const edge of data.graph.edges) {
    edgesById.set(edge.id, edge);
    if (!adjacency.has(edge.u)) adjacency.set(edge.u, []);
    adjacency.get(edge.u).push(edge);
  }

  for (const shelter of data.shelters) {
    L.circleMarker([shelter.lat, shelter.lon], {
      radius: 5,
      color: "#047857",
      fillColor: "#10b981",
      fillOpacity: 0.8,
      weight: 1
    }).bindPopup(`${shelter.name}<br>収容人数: ${shelter.capacity}`).addTo(shelterLayer);
  }

  L.circleMarker([data.breachPoint.lat, data.breachPoint.lon], {
    radius: 7,
    color: "#b45309",
    fillColor: "#f59e0b",
    fillOpacity: 0.9,
    weight: 2
  }).bindPopup(`${data.breachPoint.name}<br>${data.breachPoint.note}`).addTo(map);

  const legend = L.control({ position: "bottomright" });
  legend.onAdd = function () {
    const div = L.DomUtil.create("div", "legend");
    div.innerHTML = [
      '<div class="legend-row"><span class="swatch swatch-flood"></span>シナリオ浸水範囲</div>',
      '<div class="legend-row"><span class="swatch swatch-closed"></span>閉鎖道路</div>',
      '<div class="legend-row"><span class="swatch swatch-route"></span>避難ルート</div>',
      '<div class="legend-row"><span class="swatch swatch-outside"></span>対応地域外</div>'
    ].join("");
    return div;
  };
  legend.addTo(map);

  let activeTime = data.times[0].id;
  let activeClick = null;

  function createTimeButtons() {
    const wrap = document.getElementById("time-buttons");
    for (const time of data.times) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "time-button";
      button.textContent = time.label;
      button.dataset.timeId = time.id;
      button.setAttribute("aria-pressed", time.id === activeTime ? "true" : "false");
      button.addEventListener("click", () => setTime(time.id));
      wrap.appendChild(button);
    }
  }

  function setTime(timeId) {
    activeTime = timeId;
    document.querySelectorAll(".time-button").forEach((button) => {
      button.setAttribute("aria-pressed", button.dataset.timeId === timeId ? "true" : "false");
    });
    updateScenarioLayers();
    if (activeClick) routeFromClick(activeClick);
  }

  function updateScenarioLayers() {
    const time = data.times.find((item) => item.id === activeTime);
    const closures = data.closures[activeTime] || [];
    floodLayer.clearLayers();
    floodLayer.addData(data.floods[activeTime]);
    closedLayer.clearLayers();

    for (const edgeId of closures) {
      const edge = edgesById.get(edgeId);
      if (!edge) continue;
      L.polyline(edge.coords, {
        color: "#dc2626",
        weight: 3,
        opacity: 0.65
      }).addTo(closedLayer);
    }

    document.getElementById("status-progress").textContent = `${time.progressPercent}%`;
    document.getElementById("status-closures").textContent = `${closures.length} 本`;
    document.getElementById("status-shelters").textContent = `${data.shelters.length} 施設`;
    document.getElementById("status-area").textContent = data.supportArea.label;
  }

  function nearestNode(latlng) {
    let best = null;
    let bestScore = Infinity;
    for (const [nodeId, coord] of Object.entries(nodes)) {
      const dy = coord[0] - latlng.lat;
      const dx = coord[1] - latlng.lng;
      const score = dx * dx + dy * dy;
      if (score < bestScore) {
        best = nodeId;
        bestScore = score;
      }
    }
    return best;
  }

  class MinHeap {
    constructor() {
      this.items = [];
    }
    push(item) {
      this.items.push(item);
      this.bubbleUp(this.items.length - 1);
    }
    pop() {
      if (this.items.length === 0) return null;
      const top = this.items[0];
      const last = this.items.pop();
      if (this.items.length > 0) {
        this.items[0] = last;
        this.sinkDown(0);
      }
      return top;
    }
    bubbleUp(index) {
      while (index > 0) {
        const parent = Math.floor((index - 1) / 2);
        if (this.items[parent].dist <= this.items[index].dist) break;
        [this.items[parent], this.items[index]] = [this.items[index], this.items[parent]];
        index = parent;
      }
    }
    sinkDown(index) {
      while (true) {
        const left = index * 2 + 1;
        const right = left + 1;
        let smallest = index;
        if (left < this.items.length && this.items[left].dist < this.items[smallest].dist) smallest = left;
        if (right < this.items.length && this.items[right].dist < this.items[smallest].dist) smallest = right;
        if (smallest === index) break;
        [this.items[smallest], this.items[index]] = [this.items[index], this.items[smallest]];
        index = smallest;
      }
    }
  }

  function shortestRoute(startNode, closedSet) {
    const targetNodes = new Set(data.shelters.map((shelter) => shelter.node));
    const dist = new Map([[startNode, 0]]);
    const prev = new Map();
    const heap = new MinHeap();
    heap.push({ node: startNode, dist: 0 });

    while (heap.items.length > 0) {
      const current = heap.pop();
      if (current.dist !== dist.get(current.node)) continue;
      if (targetNodes.has(current.node)) {
        return reconstruct(startNode, current.node, current.dist, prev);
      }
      for (const edge of adjacency.get(current.node) || []) {
        if (closedSet.has(edge.id)) continue;
        const nextDist = current.dist + edge.length;
        if (nextDist < (dist.get(edge.v) ?? Infinity)) {
          dist.set(edge.v, nextDist);
          prev.set(edge.v, { node: current.node, edgeId: edge.id });
          heap.push({ node: edge.v, dist: nextDist });
        }
      }
    }
    return null;
  }

  function reconstruct(startNode, targetNode, distance, prev) {
    const edgeIds = [];
    let current = targetNode;
    while (current !== startNode) {
      const step = prev.get(current);
      if (!step) break;
      edgeIds.push(step.edgeId);
      current = step.node;
    }
    edgeIds.reverse();
    const coords = [];
    for (const edgeId of edgeIds) {
      const edge = edgesById.get(edgeId);
      if (!edge) continue;
      for (const coord of edge.coords) {
        const last = coords[coords.length - 1];
        if (!last || last[0] !== coord[0] || last[1] !== coord[1]) {
          coords.push(coord);
        }
      }
    }
    const shelter = data.shelters.find((item) => item.node === targetNode);
    return { targetNode, shelter, distance, edgeIds, coords };
  }

  function routeFromClick(latlng) {
    activeClick = latlng;
    routeLayer.clearLayers();
    markerLayer.clearLayers();
    const result = document.getElementById("route-result");

    if (!supportBounds.contains(latlng)) {
      result.innerHTML = [
        "<strong>対応地域外です</strong>",
        `${data.supportArea.label}の緑枠内をクリックしてください。`,
        "灰色の範囲は、このシミュレーション版の対象外です。"
      ].join("<br>");
      return;
    }

    L.marker(latlng).addTo(markerLayer);

    const startNode = nearestNode(latlng);
    const closedSet = new Set(data.closures[activeTime] || []);
    const route = shortestRoute(startNode, closedSet);

    if (!route || route.coords.length < 2) {
      result.textContent = "この時刻では到達可能な避難所が見つかりません。";
      return;
    }

    L.polyline(route.coords, {
      color: "#111827",
      weight: 5,
      opacity: 0.82
    }).addTo(routeLayer);

    const km = (route.distance / 1000).toFixed(2);
    result.innerHTML = [
      `<strong>${route.shelter.name}</strong>`,
      `距離: ${km} km`,
      `閉鎖回避: ${closedSet.size} 本の道路を除外`,
      `出発ノード: ${startNode}`
    ].join("<br>");
  }

  map.on("click", (event) => routeFromClick(event.latlng));
  createTimeButtons();
  updateScenarioLayers();
})();
"""
    SCENARIO_APP_JS_PATH.write_text(js, encoding="utf-8")


def main() -> None:
    ensure_output_dirs()

    final_flood = load_final_flood_area()
    scenario_flood, summary_rows = build_scenario_flood_dict(final_flood)

    edges = load_edges(str(_resolve(config.EDGES_GPKG_PATH)))
    closure_dict = build_closure_dict(edges, scenario_flood)
    diagnostics = build_closure_diagnostics(closure_dict)
    for idx, row in enumerate(diagnostics.itertuples(index=False)):
        summary_rows[idx]["closed_edge_count"] = int(row.instant_edges)

    G = ox.load_graphml(str(_resolve(config.GRAPHML_PATH)))
    payload = build_data_payload(G, scenario_flood, closure_dict, summary_rows)

    save_data_js(payload)
    save_app_js()
    save_css()
    save_html()
    save_summary_csv(summary_rows, closure_dict)

    print(f"[INFO] saved: {SCENARIO_HTML_PATH}")
    print(f"[INFO] saved: {SCENARIO_SUMMARY_CSV_PATH}")


if __name__ == "__main__":
    main()
