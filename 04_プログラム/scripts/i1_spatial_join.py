"""STEP 2: 浸水ポリゴンと道路エッジを空間照合し閉鎖候補を生成する。"""

from __future__ import annotations

import json
import pickle
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import box

import config

_CRS_METRIC = "EPSG:6690"  # JGD2011 / UTM zone 54N
_FLOOD_BUFFER_M = 30
_MESH_250M_LAT_DEG = 7.5 / 3600
_MESH_250M_LON_DEG = 11.25 / 3600


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


def load_suiboumap_hydrograph(path: str) -> dict:
    """浸水ナビ API から取得したメッシュ別ハイドログラフ JSON を読む。"""
    with open(path, encoding="utf-8") as f:
        hydrograph = json.load(f)
    if not isinstance(hydrograph.get("data"), dict):
        raise ValueError(f"浸水ナビ JSON の data 構造が不正です: {path}")
    return hydrograph


def _mesh_cell_from_center(lon: float, lat: float):
    return box(
        lon - _MESH_250M_LON_DEG / 2,
        lat - _MESH_250M_LAT_DEG / 2,
        lon + _MESH_250M_LON_DEG / 2,
        lat + _MESH_250M_LAT_DEG / 2,
    )


def build_suiboumap_flood_dict(
    hydrograph: dict,
    timestamps: list[str],
    threshold_m: float,
) -> dict[str, gpd.GeoDataFrame]:
    """浸水ナビ深度 >= threshold_m の250mメッシュを時刻別ポリゴンにする。"""
    flood_dict: dict[str, gpd.GeoDataFrame] = {}
    for ts in timestamps:
        rows: list[dict] = []
        for key_code, item in hydrograph["data"].items():
            depth = float(item.get("timestamps", {}).get(ts, 0) or 0)
            if depth < threshold_m:
                continue
            rows.append(
                {
                    "KEY_CODE": str(key_code),
                    "depth_m": depth,
                    "max_depth": float(item.get("max_depth", 0) or 0),
                    "geometry": _mesh_cell_from_center(
                        float(item["lon"]),
                        float(item["lat"]),
                    ),
                }
            )

        if rows:
            gdf = gpd.GeoDataFrame(rows, geometry="geometry", crs=config.CRS_WGS84)
            gdf = gdf.to_crs(config.CRS_JGD2011)
        else:
            gdf = gpd.GeoDataFrame(
                {"KEY_CODE": [], "depth_m": [], "max_depth": []},
                geometry=[],
                crs=config.CRS_JGD2011,
            )
        flood_dict[ts] = gdf
        print(f"[suiboumap] {ts}: {len(gdf)} flooded mesh cells")
    return flood_dict


def load_flood_source() -> tuple[str, dict[str, gpd.GeoDataFrame]]:
    source = getattr(config, "CLOSURE_SOURCE", "kml_a31a")
    if source == "suiboumap_hydrograph":
        hydro_path = Path(config.SUIBOUMAP_HYDROGRAPH_PATH)
        if hydro_path.exists():
            hydrograph = load_suiboumap_hydrograph(str(hydro_path))
            return source, build_suiboumap_flood_dict(
                hydrograph,
                config.KML_TIMESTAMPS,
                config.FLOOD_DEPTH_THRESHOLD_M,
            )
        print(f"[WARN] 浸水ナビ JSON が見つからないため KML+A31a に戻します: {hydro_path}")
    elif source != "kml_a31a":
        raise ValueError(f"未知の CLOSURE_SOURCE です: {source}")

    return "kml_a31a", load_flood_dict(config.FLOOD_PKL_PATH)


def _ensure_edge_id(edges: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    edge_id_col = "edge_id"
    base = edges.copy()
    if edge_id_col in base.columns:
        return base

    # osmnx GPKG には u/v/key 列が含まれるため "u_v_key" 形式で生成する。
    # i3_route_search.py の make_subgraph が edge_id.split("_") で
    # MultiDiGraph のエッジを特定するために必要。
    if {"u", "v", "key"}.issubset(base.columns):
        base[edge_id_col] = (
            base["u"].astype(str) + "_"
            + base["v"].astype(str) + "_"
            + base["key"].astype(str)
        )
    else:
        base[edge_id_col] = base.index.astype(str)
    return base


def _buffer_flood_geometry(flood: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    if flood.empty:
        return gpd.GeoDataFrame(geometry=[], crs=flood.crs)

    buffered = (
        gpd.GeoDataFrame(
            geometry=[
                flood.to_crs(_CRS_METRIC)
                .geometry
                .union_all()
                .buffer(_FLOOD_BUFFER_M)
            ],
            crs=_CRS_METRIC,
        )
        .to_crs(flood.crs)
    )
    return buffered[~buffered.geometry.is_empty]


def build_closure_dict(
    edges: gpd.GeoDataFrame, flood_dict: dict[str, gpd.GeoDataFrame]
) -> dict[str, list[str]]:
    edge_id_col = "edge_id"
    base = _ensure_edge_id(edges)

    # A31a グリッドセルは 5〜20m 四方の極小ポリゴン。OSM 道路中心線がセル間を
    # 通過して交差ゼロになるため、投影 CRS（EPSG:6690）で 30m バッファを適用する。
    # 30m = グリッド離散化誤差（最大 10m）＋車道幅（最大 10m）の余裕を含む値。
    closure: dict[str, list[str]] = {}
    for ts, flood_gdf in flood_dict.items():
        flood = flood_gdf if flood_gdf.crs == base.crs else flood_gdf.to_crs(base.crs)
        flood_buffered = _buffer_flood_geometry(flood)
        if flood_buffered.empty:
            closure[ts] = []
            continue
        hit = gpd.sjoin(
            base[[edge_id_col, "geometry"]],
            flood_buffered[["geometry"]],
            predicate="intersects",
            how="inner",
        )
        closure[ts] = sorted(hit[edge_id_col].astype(str).unique().tolist())
    return closure


def build_closure_diagnostics(closure_dict: dict[str, list[str]]) -> pd.DataFrame:
    rows: list[dict] = []
    previous: set[str] = set()
    cumulative: set[str] = set()
    for ts, edge_ids in closure_dict.items():
        current = set(edge_ids)
        new_edges = current - cumulative
        lost_edges = previous - current
        cumulative |= current
        rows.append(
            {
                "timestamp": ts,
                "instant_edges": len(current),
                "new_edges": len(new_edges),
                "lost_edges": len(lost_edges),
                "cumulative_edges": len(cumulative),
            }
        )
        previous = current
    return pd.DataFrame(rows)


def save_closure_dict(closure_dict: dict[str, list[str]], path: str) -> bool:
    try:
        with open(path, "wb") as f:
            pickle.dump(closure_dict, f)
    except PermissionError:
        if Path(path).exists():
            with open(path, "rb") as f:
                pickle.load(f)
            print(f"[WARN] 既存PKLを上書きできないため保持: {path}")
            return False
        raise
    return True


def save_closure_diagnostics(diagnostics: pd.DataFrame, path: str) -> bool:
    try:
        diagnostics.to_csv(path, index=False)
    except PermissionError:
        if Path(path).exists():
            pd.read_csv(path, nrows=1)
            print(f"[WARN] 既存診断CSVを上書きできないため保持: {path}")
            return False
        raise
    return True


def main() -> None:
    ensure_output_dir(config.OUT_CLOSURE_DIR)
    edges = load_edges(config.EDGES_GPKG_PATH)
    source, flood_dict = load_flood_source()
    print(f"[INFO] closure source: {source}")
    closure = build_closure_dict(edges, flood_dict)
    diagnostics = build_closure_diagnostics(closure)
    for row in diagnostics.itertuples(index=False):
        print(
            f"{row.timestamp}: instant={row.instant_edges}, "
            f"new={row.new_edges}, lost={row.lost_edges}, "
            f"cumulative={row.cumulative_edges}"
        )
    if save_closure_dict(closure, config.CLOSURE_PKL_PATH):
        print(f"[INFO] saved: {config.CLOSURE_PKL_PATH}")
    if save_closure_diagnostics(diagnostics, config.CLOSURE_DIAGNOSTICS_CSV_PATH):
        print(f"[INFO] saved: {config.CLOSURE_DIAGNOSTICS_CSV_PATH}")


if __name__ == "__main__":
    main()
