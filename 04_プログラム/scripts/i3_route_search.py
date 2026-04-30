"""STEP 4: 迂回ルート検索・逃げ遅れカウント。"""

from __future__ import annotations

import json
import pickle
from pathlib import Path

import folium
import geopandas as gpd
import networkx as nx
import osmnx as ox
import pandas as pd

import config


def ensure_output_dirs() -> None:
    Path(config.OUT_AGENTS_DIR).mkdir(parents=True, exist_ok=True)
    Path(config.OUT_ROUTES_DIR).mkdir(parents=True, exist_ok=True)


def meshcode_to_lon_lat(key_code: str) -> tuple[float, float]:
    key = str(key_code).zfill(10)
    p, u = int(key[0:2]), int(key[2:4])
    _q, v = int(key[4]), int(key[5])
    r, w = int(key[6]), int(key[7])
    s, x = int(key[8]), int(key[9])
    lat = p / 1.5 + (r * 30 + s * 15 / 2) / 3600
    lon = 100 + u + v * 0.125 + w * 0.125 / 2 + x * 0.125 / 4
    return lon, lat


def _read_mesh_table(mesh_file: str) -> pd.DataFrame:
    raw = pd.read_csv(mesh_file, encoding="shift_jis", header=None, dtype=str)
    header = raw.iloc[0].tolist()
    if any(("KEY_CODE" in str(x)) or ("メッシュ" in str(x)) for x in header):
        df = raw.iloc[2:].copy()
        df.columns = header
    else:
        df = raw.copy()
        df.columns = [f"col_{i}" for i in range(df.shape[1])]
    return df


def _find_col(candidates: list[str], columns: list[str], default: str) -> str:
    for c in columns:
        if any(k in c for k in candidates):
            return c
    return default


def load_mesh_origins(mesh_file: str, flood_poly: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    df = _read_mesh_table(mesh_file)
    key_col = _find_col(["KEY_CODE", "メッシュ"], list(df.columns), "col_0")
    total_col = _find_col(["総数", "人口", "総人口"], list(df.columns), "col_9")
    elderly_col = _find_col(["65", "高齢"], list(df.columns), "col_22")

    work = df[[key_col, total_col, elderly_col]].copy()
    work.columns = ["KEY_CODE", "total_pop", "elderly_pop"]
    work["KEY_CODE"] = work["KEY_CODE"].astype(str).str.zfill(10)
    work = work[work["KEY_CODE"].str[:6].isin(["543907", "543917"])].copy()

    work[["lon", "lat"]] = work["KEY_CODE"].apply(lambda k: pd.Series(meshcode_to_lon_lat(k)))
    work["total_pop"] = pd.to_numeric(work["total_pop"], errors="coerce").fillna(0).astype(int)
    work["elderly_pop"] = pd.to_numeric(work["elderly_pop"], errors="coerce").fillna(0).astype(int)

    gdf = gpd.GeoDataFrame(work, geometry=gpd.points_from_xy(work["lon"], work["lat"]), crs=config.CRS_WGS84)
    flood_wgs = flood_poly.to_crs(config.CRS_WGS84)
    joined = gpd.sjoin(gdf, flood_wgs[["geometry"]], how="inner", predicate="intersects")
    joined = joined.drop(columns=[c for c in ["index_right"] if c in joined.columns])
    return joined


def load_shelters(dbf_path: str) -> gpd.GeoDataFrame:
    shp_path = str(Path(dbf_path).with_suffix(".shp"))
    gdf = gpd.read_file(shp_path, engine="pyogrio")
    gdf = gdf[(gdf["P20_001"] == config.JOSO_CODE) & (gdf["P20_007"] == "1")].copy()
    gdf = gdf.to_crs(config.CRS_WGS84)
    gdf["name"] = gdf.get("P20_002", "unknown")
    gdf["capacity"] = pd.to_numeric(gdf.get("P20_005", 0), errors="coerce").fillna(0).astype(int)
    gdf["lon"] = gdf.geometry.x
    gdf["lat"] = gdf.geometry.y
    return gdf[["name", "capacity", "lon", "lat", "geometry"]]


def make_subgraph(G: nx.MultiDiGraph, closed_edges: list[str]) -> nx.MultiDiGraph:
    sub = G.copy()
    for edge_id in closed_edges:
        try:
            u, v, k = edge_id.split("_")
            sub.remove_edge(int(u), int(v), int(k))
        except Exception:
            continue
    return sub


def find_nearest_node(G: nx.MultiDiGraph, lon: float, lat: float) -> int:
    return int(ox.distance.nearest_nodes(G, lon, lat))


def compute_route(G: nx.MultiDiGraph, origin_node: int, dest_nodes: list[int]) -> list[int] | None:
    best: list[int] | None = None
    best_len = float("inf")
    for d in dest_nodes:
        try:
            route = nx.shortest_path(G, origin_node, d, weight="length")
            length = nx.path_weight(G, route, weight="length")
            if length < best_len:
                best = route
                best_len = length
        except nx.NetworkXNoPath:
            continue
    return best


def run_all_timesteps(
    G: nx.MultiDiGraph,
    closure_timeline: dict[str, list[str]],
    origins: gpd.GeoDataFrame,
    destinations: gpd.GeoDataFrame,
) -> dict[str, dict[str, list]]:
    dest_nodes = [find_nearest_node(G, row.lon, row.lat) for row in destinations.itertuples()]
    results: dict[str, dict[str, list]] = {}

    for idx, ts in enumerate(config.KML_TIMESTAMPS):
        closed = closure_timeline.get(ts, [])
        sub = make_subgraph(G, closed)
        unreachable: list[dict] = []
        routes: list[list[int]] = []

        for row in origins.itertuples():
            o = find_nearest_node(sub, row.lon, row.lat)
            route = compute_route(sub, o, dest_nodes)
            if route is None:
                unreachable.append(
                    {
                        "timestamp": ts,
                        "KEY_CODE": row.KEY_CODE,
                        "total_pop": int(row.total_pop),
                        "elderly_pop": int(row.elderly_pop),
                    }
                )
            else:
                routes.append(route)

        results[ts] = {"unreachable": unreachable, "routes": routes}
        _save_routes_map(sub, origins, routes, f"{config.OUT_ROUTES_DIR}/evacuation_routes_t{idx}.html")
        print(f"{ts}: unreachable={len(unreachable)}")

    return results


def _save_routes_map(G: nx.MultiDiGraph, origins: gpd.GeoDataFrame, routes: list[list[int]], out_html: str) -> None:
    fmap = folium.Map(location=[36.05, 140.0], zoom_start=11)
    folium.GeoJson(origins[["geometry"]].to_crs(config.CRS_WGS84), name="origins").add_to(fmap)

    for route in routes[:200]:
        coords = [(G.nodes[n]["y"], G.nodes[n]["x"]) for n in route if n in G.nodes]
        if len(coords) >= 2:
            folium.PolyLine(coords, weight=2, opacity=0.5).add_to(fmap)
    fmap.save(out_html)


def main() -> None:
    ensure_output_dirs()

    G = ox.load_graphml(config.GRAPHML_PATH)
    with open(config.CLOSURE_JSON_PATH, encoding="utf-8") as f:
        closure_timeline = json.load(f)
    with open(config.FLOOD_PKL_PATH, "rb") as f:
        flood_dict = pickle.load(f)

    first_flood = flood_dict[config.KML_TIMESTAMPS[0]]
    origins = load_mesh_origins(config.MESH_FILE, first_flood)
    shelters = load_shelters(config.SHELTER_DBF)

    origins[["KEY_CODE", "lon", "lat", "total_pop", "elderly_pop"]].to_csv(config.ORIGINS_CSV_PATH, index=False)
    shelters[["name", "capacity", "lon", "lat"]].to_csv(config.SHELTERS_CSV_PATH, index=False)

    results = run_all_timesteps(G, closure_timeline, origins, shelters)
    unreachable_rows = [row for ts in results for row in results[ts]["unreachable"]]
    pd.DataFrame(unreachable_rows, columns=["timestamp", "KEY_CODE", "total_pop", "elderly_pop"]).to_csv(config.UNREACHABLE_PATH, index=False)
    print(f"[INFO] saved: {config.UNREACHABLE_PATH}")


if __name__ == "__main__":
    main()
