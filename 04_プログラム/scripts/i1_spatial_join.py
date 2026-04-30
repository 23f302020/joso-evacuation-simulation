"""コンフリクト解消済み。STEP 2: 浸水ポリゴンと道路エッジの空間照合。"""

from __future__ import annotations

import pickle
from pathlib import Path

import geopandas as gpd

import config


def ensure_output_dir(path: str) -> None:
    Path(path).mkdir(parents=True, exist_ok=True)


def load_edges(path: str) -> gpd.GeoDataFrame:
    edges = gpd.read_file(path)
    if edges.crs is None or edges.crs.to_string() != config.CRS_JGD2011:
        edges = edges.to_crs(config.CRS_JGD2011)
    return edges


def load_flood_dict(path: str) -> dict[str, gpd.GeoDataFrame]:
    with open(path, "rb") as f:
        return pickle.load(f)


def build_closure_dict(edges: gpd.GeoDataFrame, flood_dict: dict[str, gpd.GeoDataFrame]) -> dict[str, list[str]]:
    base = edges.copy()
    if not {"u", "v", "key"}.issubset(base.columns):
        raise KeyError("edges must contain u, v, key columns")

    assert base.crs is not None and base.crs.to_epsg() == 6668

    base["edge_id"] = base.apply(lambda r: f"{int(r.u)}_{int(r.v)}_{int(r.key)}", axis=1)

    closure: dict[str, list[str]] = {}
    for ts, flood_gdf in flood_dict.items():
        flood = flood_gdf if flood_gdf.crs == base.crs else flood_gdf.to_crs(base.crs)
        assert flood.crs is not None and flood.crs.to_epsg() == 6668
        hit = gpd.sjoin(base[["edge_id", "geometry"]], flood[["geometry"]], predicate="intersects", how="inner")
        closure[ts] = sorted(hit["edge_id"].astype(str).unique().tolist())
    return closure


def save_closure_dict(closure_dict: dict[str, list[str]], path: str) -> None:
    with open(path, "wb") as f:
        pickle.dump(closure_dict, f)


def main() -> None:
    ensure_output_dir(config.OUT_CLOSURE_DIR)
    edges = load_edges(config.EDGES_GPKG_PATH)
    flood_dict = load_flood_dict(config.FLOOD_PKL_PATH)
    closure = build_closure_dict(edges, flood_dict)
    save_closure_dict(closure, config.CLOSURE_PKL_PATH)
    for ts, ids in closure.items():
        print(f"{ts}: {len(ids)} edges closed")


if __name__ == "__main__":
    main()
