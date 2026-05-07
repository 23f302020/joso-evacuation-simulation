"""市区町村別シナリオ型避難ルートシミュレーション HTML 生成スクリプト。

使い方:
    python city_scenario.py --code 08235          # つくばみらい市
    python city_scenario.py --code 08235 08227    # 複数指定

出力:
    output/scenario_cities/{code}/
        scenario_route_simulation.html
        assets/data.js
        assets/app.js
        assets/style.css
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

import geopandas as gpd
import osmnx as ox
import pandas as pd
from shapely.geometry import Point, mapping
from shapely import wkt

import config
from e1_load_flood_data import load_a31a_gml
from i1_spatial_join import build_closure_dict, load_edges
from i3_route_search import find_nearest_node

SCRIPT_DIR = Path(__file__).resolve().parent
CRS_METRIC = "EPSG:6690"

_ELAPSED_H = [5.2, 17.2, 29.2, 41.2, 53.2, 65.2, 77.2, 141.5]
_TOTAL_H = 141.5
SCENARIO_PROGRESS = [h / _TOTAL_H for h in _ELAPSED_H]


def _resolve(path: str) -> Path:
    return (SCRIPT_DIR / path).resolve()


# ---------------------------------------------------------------------------
# データ読み込み
# ---------------------------------------------------------------------------

def load_city_boundary(city_code: str) -> gpd.GeoDataFrame:
    n03 = gpd.read_file(str(_resolve(config.N03_SHP_PATH)), engine="pyogrio")
    boundary = n03[n03["N03_007"] == city_code].copy()
    if boundary.empty:
        raise ValueError(f"N03 に {city_code} が見つかりません")
    return boundary.to_crs(config.CRS_JGD2011)


def load_a31a_for_city(city_code: str, city_boundary: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """A31a (08_10 + 08_20) を市区町村境界でクリップして返す。

    ディレクトリごとに読み込みを試みて、失敗した場合は警告して次を試す。
    """
    from p1_city_road_network import A31A_COVERAGE, A31A_EXCLUDED
    coverage = A31A_COVERAGE.get(city_code, [])
    if not coverage:
        reason = A31A_EXCLUDED.get(city_code, "要調査市区町村")
        raise RuntimeError(f"{city_code}: A31a洪水データなし（{reason}）")

    dir_map = {
        "08_10": str(_resolve(config.GML_DIR)),
        "08_20": str(_resolve(config.A31a_GML_DIR_20)),
    }
    gdfs: list[gpd.GeoDataFrame] = []
    for key in coverage:
        gml_dir = dir_map.get(key)
        if not gml_dir:
            continue
        try:
            gdf = load_a31a_gml(gml_dir)
            gdfs.append(gdf)
        except RuntimeError as e:
            print(f"[WARN] {city_code} A31a {key}: {e} → スキップ")

    if not gdfs:
        raise RuntimeError(f"{city_code}: A31a ポリゴンを読み込めませんでした")

    combined = pd.concat(gdfs, ignore_index=True)
    a31a = gpd.GeoDataFrame(combined, geometry="geometry", crs=config.CRS_JGD2011)

    city_union = gpd.GeoDataFrame(
        geometry=[city_boundary.geometry.union_all()],
        crs=config.CRS_JGD2011,
    )
    joined = gpd.sjoin(a31a, city_union, how="inner", predicate="intersects")
    result = a31a.loc[joined.index.unique()].copy()
    if result.empty:
        raise RuntimeError(f"{city_code}: 市区町村内に A31a ポリゴンが見つかりません")
    print(f"[flood] {city_code}: {len(result)} ポリゴン (A31a waterDepth>={config.FLOOD_DEPTH_THRESHOLD})")
    return result


def load_city_network(city_code: str):
    """道路NW (GraphML + edges.gpkg) を読み込む。常総市は旧パスにフォールバック。"""
    from p1_city_road_network import graphml_path, gpkg_path
    gml = graphml_path(city_code)
    gpkg = gpkg_path(city_code)

    if not gml.exists() and city_code == "08211":
        gml = _resolve(config.GRAPHML_PATH)
        gpkg = _resolve(config.EDGES_GPKG_PATH)

    if not gml.exists():
        raise FileNotFoundError(
            f"道路NW未取得: {gml}\n"
            "  → python p1_city_road_network.py --code {city_code} を実行してください"
        )

    G = ox.load_graphml(str(gml))
    edges = load_edges(str(gpkg))
    print(f"[network] {city_code}: {len(G.nodes())} nodes, {len(G.edges())} edges")
    return G, edges


def load_gsi_shelters(city_code: str) -> gpd.GeoDataFrame:
    """GSI 緊急避難場所（2号）から市区町村の洪水対応施設を返す。"""
    csv_path = str(_resolve(config.GSI_SHELTERS_2_CSV))
    df = pd.read_csv(csv_path, encoding="utf-8-sig", dtype=str).fillna("")
    df["_code"] = df["共通ID"].astype(str).str.extract(r"E(08\d{3})")
    flood_flag = df["洪水"].astype(str).str.strip()
    flood_df = df[(df["_code"] == city_code) & (flood_flag == "1")].copy()
    if flood_df.empty:
        flood_df = df[df["_code"] == city_code].copy()
        print(f"[WARN] {city_code}: 洪水=1施設なし → 全 {len(flood_df)} 件を使用")
    flood_df["緯度"] = pd.to_numeric(flood_df["緯度"], errors="coerce")
    flood_df["経度"] = pd.to_numeric(flood_df["経度"], errors="coerce")
    flood_df = flood_df.dropna(subset=["緯度", "経度"]).copy()
    gdf = gpd.GeoDataFrame(
        flood_df,
        geometry=gpd.points_from_xy(flood_df["経度"], flood_df["緯度"]),
        crs=config.CRS_WGS84,
    )
    gdf["name"] = gdf["施設・場所名"]
    gdf["capacity"] = 0
    gdf["lon"] = gdf.geometry.x
    gdf["lat"] = gdf.geometry.y
    print(f"[shelters] {city_code}: {len(gdf)} 施設 (GSI 2号)")
    return gdf[["name", "capacity", "lon", "lat", "geometry"]]


# ---------------------------------------------------------------------------
# シナリオ構築
# ---------------------------------------------------------------------------

def compute_breach_proxy(a31a_gdf: gpd.GeoDataFrame) -> dict[str, Any]:
    """A31a 洪水ポリゴン群の重心を破堤点の代替として使用する。"""
    centroid_m = a31a_gdf.to_crs(CRS_METRIC).geometry.union_all().centroid
    pt = gpd.GeoSeries([centroid_m], crs=CRS_METRIC).to_crs(config.CRS_WGS84).iloc[0]
    return {
        "lat": round(float(pt.y), 6),
        "lon": round(float(pt.x), 6),
        "name": "浸水範囲中心（推定）",
        "note": "A31a浸水想定区域の重心点を破堤点代替として使用",
    }


def build_scenario_flood_dict(
    a31a_gdf: gpd.GeoDataFrame,
    breach_proxy: dict[str, Any],
) -> tuple[dict[str, gpd.GeoDataFrame], list[dict[str, Any]]]:
    metric = a31a_gdf.to_crs(CRS_METRIC).copy()
    breach_pt = (
        gpd.GeoSeries([Point(breach_proxy["lon"], breach_proxy["lat"])], crs=config.CRS_WGS84)
        .to_crs(CRS_METRIC)
        .iloc[0]
    )
    distances = metric.geometry.centroid.distance(breach_pt)
    metric["_dist"] = distances
    scenario: dict[str, gpd.GeoDataFrame] = {}
    summary: list[dict[str, Any]] = []
    for idx, (ts, progress) in enumerate(zip(config.KML_TIMESTAMPS, SCENARIO_PROGRESS)):
        threshold = distances.quantile(progress)
        sel = metric[distances <= threshold].copy()
        if sel.empty:
            sel = metric.nsmallest(1, "_dist").copy()
        sel = sel.drop(columns=["_dist"], errors="ignore").to_crs(config.CRS_JGD2011)
        scenario[ts] = sel
        summary.append(
            {
                "id": f"t{idx}",
                "timestamp": ts,
                "progress_ratio": progress,
                "flood_polygon_count": len(sel),
            }
        )
    return scenario, summary


# ---------------------------------------------------------------------------
# ペイロード構築（JS用データ）
# ---------------------------------------------------------------------------

def _thin_coords(coords: list, max_points: int = 10) -> list:
    if len(coords) <= max_points:
        return coords
    step = max(1, math.ceil(len(coords) / (max_points - 1)))
    thinned = coords[::step]
    if thinned[-1] != coords[-1]:
        thinned.append(coords[-1])
    return thinned


def _edge_coords(data: dict, u_data: dict, v_data: dict) -> list:
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
        str(nid): [round(float(d["y"]), 6), round(float(d["x"]), 6)]
        for nid, d in G.nodes(data=True)
    }
    edges = []
    for u, v, key, data in G.edges(keys=True, data=True):
        edges.append(
            {
                "id": f"{u}_{v}_{key}",
                "u": str(u),
                "v": str(v),
                "length": round(float(data.get("length") or 1.0), 2),
                "coords": _edge_coords(data, G.nodes[u], G.nodes[v]),
            }
        )
    return {"nodes": nodes, "edges": edges}


def _compact_flood_geojson(gdf: gpd.GeoDataFrame) -> dict[str, Any]:
    union = gdf.to_crs(config.CRS_WGS84).geometry.union_all().simplify(0.00004, preserve_topology=True)
    return {"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {}, "geometry": mapping(union)}]}


def build_data_payload(
    G,
    city_code: str,
    city_name: str,
    city_boundary: gpd.GeoDataFrame,
    scenario_flood: dict[str, gpd.GeoDataFrame],
    closure_dict: dict[str, list[str]],
    summary_rows: list[dict[str, Any]],
    shelters: gpd.GeoDataFrame,
    breach_proxy: dict[str, Any],
) -> dict[str, Any]:
    bounds_wgs = city_boundary.to_crs(config.CRS_WGS84).total_bounds  # (minx, miny, maxx, maxy)
    buf_lat = max((bounds_wgs[3] - bounds_wgs[1]) * 0.10, 0.01)
    buf_lon = max((bounds_wgs[2] - bounds_wgs[0]) * 0.10, 0.01)
    lat_pad = max((bounds_wgs[3] - bounds_wgs[1]) * 0.15, 0.01)
    lon_pad = max((bounds_wgs[2] - bounds_wgs[0]) * 0.15, 0.01)
    support_area = {
        "label": f"{city_name} 道路ネットワーク範囲",
        "bounds": [
            [round(bounds_wgs[1] - buf_lat, 6), round(bounds_wgs[0] - buf_lon, 6)],
            [round(bounds_wgs[3] + buf_lat, 6), round(bounds_wgs[2] + buf_lon, 6)],
        ],
        "maxBounds": [
            [round(bounds_wgs[1] - lat_pad, 6), round(bounds_wgs[0] - lon_pad, 6)],
            [round(bounds_wgs[3] + lat_pad, 6), round(bounds_wgs[2] + lon_pad, 6)],
        ],
    }
    map_center = [
        round((bounds_wgs[1] + bounds_wgs[3]) / 2, 6),
        round((bounds_wgs[0] + bounds_wgs[2]) / 2, 6),
    ]

    shelter_rows = []
    for idx, row in enumerate(shelters.itertuples(index=False)):
        node = find_nearest_node(G, float(row.lon), float(row.lat))
        shelter_rows.append(
            {
                "id": f"shelter_{idx}",
                "name": str(row.name),
                "capacity": int(row.capacity),
                "lat": round(float(row.lat), 6),
                "lon": round(float(row.lon), 6),
                "node": str(node),
            }
        )

    closures = {
        f"t{idx}": closure_dict.get(ts, [])
        for idx, ts in enumerate(config.KML_TIMESTAMPS)
    }
    times = [
        {
            "id": f"t{idx}",
            "label": f"t{idx}",
            "timestamp": row["timestamp"],
            "progressPercent": round(float(row["progress_ratio"]) * 100),
        }
        for idx, row in enumerate(summary_rows)
    ]
    floods = {
        f"t{idx}": _compact_flood_geojson(scenario_flood[ts])
        for idx, ts in enumerate(config.KML_TIMESTAMPS)
    }

    return {
        "version": f"city_scenario_{city_code}",
        "title": f"{city_name} シナリオ型避難ルート",
        "map": {"center": map_center, "zoom": 12},
        "supportArea": support_area,
        "breachPoint": breach_proxy,
        "times": times,
        "floods": floods,
        "closures": closures,
        "graph": build_graph_payload(G),
        "shelters": shelter_rows,
    }


# ---------------------------------------------------------------------------
# ファイル出力
# ---------------------------------------------------------------------------

def save_output(payload: dict[str, Any], out_dir: Path, city_name: str) -> None:
    assets_dir = out_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    data_js = assets_dir / "data.js"
    data_js.write_text(
        "window.SCENARIO_V2_DATA = "
        + json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        + ";\n",
        encoding="utf-8",
    )

    _write_css(assets_dir / "style.css")
    _write_app_js(assets_dir / "app.js")
    _write_html(out_dir / "scenario_route_simulation.html", city_name)

    print(f"[done] {out_dir / 'scenario_route_simulation.html'}")


def _write_html(path: Path, city_name: str) -> None:
    html = f"""<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{city_name} 避難ルートシミュレーション</title>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
  <link rel="stylesheet" href="assets/style.css">
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js" defer></script>
  <script src="assets/data.js" defer></script>
  <script src="assets/app.js" defer></script>
</head>
<body>
  <main class="app-shell">
    <aside class="panel" aria-label="シミュレーション操作">
      <p class="eyebrow">市区町村別シナリオ</p>
      <h1>{city_name}</h1>
      <p class="lead">時刻を選び、地図上の任意地点をクリックすると、浸水道路を避けて到達可能な最寄り避難所までのルートを検索します。</p>
      <section class="control-group">
        <h2>時刻</h2>
        <div id="time-buttons" class="time-grid"></div>
      </section>
      <section class="control-group">
        <h2>状態</h2>
        <dl class="status-list">
          <div><dt>浸水進行</dt><dd id="status-progress">-</dd></div>
          <div><dt>閉鎖道路</dt><dd id="status-closures">-</dd></div>
          <div><dt>避難所</dt><dd id="status-shelters">-</dd></div>
          <div><dt>対象地域</dt><dd id="status-area">-</dd></div>
        </dl>
      </section>
      <section class="control-group">
        <h2>検索結果</h2>
        <div id="route-result" class="result-box">地図上の地点をクリックしてください。</div>
      </section>
      <a class="back-link" href="../../index.html">トップページへ戻る</a>
    </aside>
    <section class="map-wrap" aria-label="シミュレーション地図">
      <div id="map"></div>
    </section>
  </main>
</body>
</html>
"""
    path.write_text(html, encoding="utf-8")


def _write_css(path: Path) -> None:
    path.write_text(""":root{color-scheme:light;--bg:#ffffff;--text:#1f2933;--muted:#6b7280;--line:#d9dee5;--surface:#f8fafc;--surface-hover:#eef2f7;--accent:#2563eb;--danger:#dc2626}
*{box-sizing:border-box}
body{margin:0;min-height:100vh;background:var(--bg);color:var(--text);font-family:"Yu Gothic","Meiryo",system-ui,sans-serif}
.app-shell{display:grid;grid-template-columns:340px minmax(0,1fr);min-height:100vh}
.panel{border-right:1px solid var(--line);padding:28px 24px;background:var(--bg);overflow-y:auto}
.eyebrow{margin:0;color:var(--muted);font-size:13px}
h1{margin:4px 0 8px;font-size:26px;line-height:1.25}
.lead{margin:0 0 24px;color:var(--muted);font-size:14px;line-height:1.7}
.control-group{margin-top:24px}
h2{margin:0 0 10px;font-size:15px}
.time-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px}
.time-button{min-height:42px;border:1px solid var(--line);border-radius:8px;background:var(--bg);color:var(--text);font:inherit;cursor:pointer}
.time-button:hover,.time-button:focus-visible{border-color:var(--accent);background:var(--surface-hover);outline:none}
.time-button[aria-pressed="true"]{border-color:var(--accent);background:#eff6ff;color:#1d4ed8;font-weight:700}
.status-list{margin:0}
.status-list div{display:flex;align-items:baseline;justify-content:space-between;gap:12px;padding:8px 0;border-bottom:1px solid var(--line)}
dt{color:var(--muted);font-size:13px}
dd{margin:0;font-weight:700}
.result-box{min-height:112px;border:1px solid var(--line);border-radius:8px;background:var(--surface);padding:12px;font-size:14px;line-height:1.6}
.result-box strong{display:block;margin-bottom:4px}
.back-link{display:inline-flex;margin-top:24px;color:var(--accent);font-size:14px;text-decoration:none}
.map-wrap,#map{min-height:100vh}
.legend{border:1px solid var(--line);border-radius:8px;background:rgba(255,255,255,0.95);padding:10px 12px;line-height:1.7;font-size:13px}
.legend-row{display:flex;align-items:center;gap:8px}
.swatch{width:18px;height:4px;border-radius:99px;display:inline-block}
.swatch-flood{height:12px;background:rgba(37,99,235,0.3);border:1px solid #1d4ed8}
.swatch-closed{background:var(--danger)}
.swatch-route{background:#111827}
.swatch-outside{height:12px;background:rgba(31,41,55,0.18);border:1px solid rgba(31,41,55,0.4)}
@media(max-width:860px){.app-shell{grid-template-columns:1fr}.panel{border-right:0;border-bottom:1px solid var(--line)}.map-wrap,#map{min-height:66vh}}
""", encoding="utf-8")


def _write_app_js(path: Path) -> None:
    """v2 の app.js をコピーする。未生成の場合は v2 モジュールから生成する。"""
    import shutil
    v2_app_js = (SCRIPT_DIR / ".." / "output" / "scenario_v2" / "assets" / "scenario_v2_app.js").resolve()
    if v2_app_js.exists():
        shutil.copy2(str(v2_app_js), str(path))
        return
    # v2 未実行の場合は save_app_js() を呼んで生成してからコピー
    from v2_scenario_route_simulation import save_app_js, SCENARIO_APP_JS_PATH
    save_app_js()
    shutil.copy2(str(SCENARIO_APP_JS_PATH), str(path))


# ---------------------------------------------------------------------------
# メイン処理
# ---------------------------------------------------------------------------

def process_city(city_code: str) -> None:
    from p1_city_road_network import MUNICIPALITIES
    city_name = dict(MUNICIPALITIES).get(city_code, city_code)
    print(f"\n{'='*60}")
    print(f"  {city_name} ({city_code})")
    print(f"{'='*60}")

    city_boundary = load_city_boundary(city_code)
    a31a_gdf = load_a31a_for_city(city_code, city_boundary)
    G, edges = load_city_network(city_code)
    shelters = load_gsi_shelters(city_code)
    breach_proxy = compute_breach_proxy(a31a_gdf)
    scenario_flood, summary_rows = build_scenario_flood_dict(a31a_gdf, breach_proxy)
    closure_dict = build_closure_dict(edges, scenario_flood)

    for idx, row in enumerate(summary_rows):
        row["closed_edge_count"] = len(closure_dict.get(config.KML_TIMESTAMPS[idx], []))
    print(f"[closure] 閉鎖エッジ数: {[row['closed_edge_count'] for row in summary_rows]}")

    payload = build_data_payload(
        G, city_code, city_name, city_boundary,
        scenario_flood, closure_dict, summary_rows, shelters, breach_proxy,
    )

    out_dir = Path(str(_resolve(config.OUT_SCENARIO_CITIES_DIR))) / city_code
    save_output(payload, out_dir, city_name)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="市区町村別シナリオ型避難ルートシミュレーション HTML 生成"
    )
    parser.add_argument("--code", nargs="+", required=True, help="市区町村コード（例: 08235 08227）")
    args = parser.parse_args()

    errors: list[tuple[str, str]] = []
    for code in args.code:
        try:
            process_city(code)
        except FileNotFoundError as e:
            print(f"[SKIP] {code}: {e}", file=sys.stderr)
            errors.append((code, str(e)))
        except Exception as e:
            print(f"[ERROR] {code}: {e}", file=sys.stderr)
            errors.append((code, str(e)))

    if errors:
        print(f"\n失敗: {len(errors)} 件")
        for code, msg in errors:
            print(f"  {code}: {msg}")
    else:
        print(f"\n完了: {len(args.code)} 市区町村")


if __name__ == "__main__":
    main()
